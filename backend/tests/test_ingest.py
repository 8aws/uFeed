from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.source import Source
from app.services.ingest import (
    compute_next_fetch,
    parse_feed,
    refresh_source,
    store_articles,
)

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Example Feed</title>
  <link>https://example.com</link>
  <language>es</language>
  <item>
    <title>First post</title>
    <link>https://example.com/1</link>
    <guid>https://example.com/1</guid>
    <author>alice@example.com</author>
    <description>Hello world</description>
    <pubDate>Mon, 01 Sep 2025 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Second post</title>
    <link>https://example.com/2</link>
    <guid>https://example.com/2</guid>
    <description>Another one</description>
    <pubDate>Tue, 02 Sep 2025 12:00:00 GMT</pubDate>
  </item>
</channel></rss>
"""


async def _make_source(db: AsyncSession, url: str = "https://example.com/feed.xml") -> Source:
    source = Source(feed_url=f"{url}?{uuid.uuid4().hex}", fetch_interval_s=900)
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --- Pure parsing ------------------------------------------------------------


def test_parse_feed_normalises_entries() -> None:
    parsed = parse_feed(RSS)
    assert parsed.title == "Example Feed"
    assert parsed.site_url == "https://example.com"
    assert parsed.lang == "es"
    assert len(parsed.articles) == 2
    first = parsed.articles[0]
    assert first.guid == "https://example.com/1"
    assert first.title == "First post"
    assert first.published_at == datetime(2025, 9, 1, 10, 0, 0, tzinfo=UTC)
    assert first.lang == "es"


def test_compute_next_fetch_backoff() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    base = compute_next_fetch(900, 0, now=now)
    assert (base - now).total_seconds() == 900
    # error_count grows the delay exponentially...
    d1 = (compute_next_fetch(900, 1, now=now) - now).total_seconds()
    d2 = (compute_next_fetch(900, 2, now=now) - now).total_seconds()
    assert d1 == 1800 and d2 == 3600
    # ...but is capped.
    capped = (compute_next_fetch(900, 20, now=now) - now).total_seconds()
    assert capped == 21_600


# --- Storage / dedup ---------------------------------------------------------


async def _count(db: AsyncSession, source_id: uuid.UUID) -> int:
    res = await db.execute(select(func.count()).where(Article.source_id == source_id))
    return res.scalar_one()


async def test_store_articles_is_idempotent(db_session: AsyncSession) -> None:
    source = await _make_source(db_session)
    parsed = parse_feed(RSS)

    n1 = await store_articles(db_session, source, parsed)
    await db_session.commit()
    assert n1 == 2
    assert await _count(db_session, source.id) == 2

    # Re-ingesting the same feed inserts nothing new.
    n2 = await store_articles(db_session, source, parsed)
    await db_session.commit()
    assert n2 == 0
    assert await _count(db_session, source.id) == 2


# --- Full refresh (mocked HTTP) ---------------------------------------------


async def test_refresh_source_ok_then_not_modified(db_session: AsyncSession) -> None:
    source = await _make_source(db_session)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if request.headers.get("If-None-Match") == 'W/"v1"':
            return httpx.Response(304)
        return httpx.Response(200, content=RSS, headers={"ETag": 'W/"v1"'})

    async with _client(handler) as client:
        r1 = await refresh_source(db_session, client, source)
        assert r1.status == "ok"
        assert await _count(db_session, source.id) == 2
        assert source.etag == 'W/"v1"'
        assert source.title == "Example Feed"
        assert source.error_count == 0
        assert source.next_fetch_at is not None

        # Second call sends If-None-Match and gets 304 -> no new rows.
        r2 = await refresh_source(db_session, client, source)
        assert r2.status == "not_modified"
        assert await _count(db_session, source.id) == 2
    # >=2: the first OK also triggers best-effort og:image backfill fetches.
    assert calls["n"] >= 2


async def test_refresh_source_error_backs_off(db_session: AsyncSession) -> None:
    source = await _make_source(db_session)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with _client(handler) as client:
        before = datetime.now(UTC)
        r = await refresh_source(db_session, client, source)
        assert r.status == "error"
        assert source.error_count == 1
        # Backed off to now + interval*2^1 = +1800s, well beyond the base interval.
        assert source.next_fetch_at > before
        assert (source.next_fetch_at - before).total_seconds() > 900
