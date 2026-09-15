from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from time import struct_time

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.article import Article
from app.models.source import Source


@dataclass(slots=True)
class ParsedArticle:
    guid: str
    url: str | None
    title: str | None
    author: str | None
    content_html: str | None
    summary: str | None
    lang: str | None
    published_at: datetime | None


@dataclass(slots=True)
class ParsedFeed:
    title: str | None
    site_url: str | None
    lang: str | None
    articles: list[ParsedArticle]


@dataclass(slots=True)
class FetchResult:
    status: str  # "ok" | "not_modified" | "error"
    content: bytes | None = None
    etag: str | None = None
    last_modified: str | None = None
    error: str | None = None


# --- Parsing -----------------------------------------------------------------


def _struct_to_dt(st: struct_time | None) -> datetime | None:
    if st is None:
        return None
    # feedparser normalises parsed dates to UTC.
    return datetime(*st[:6], tzinfo=UTC)


def _entry_guid(entry: dict) -> str:
    for key in ("id", "guid", "link"):
        value = entry.get(key)
        if value:
            return str(value)
    basis = f"{entry.get('title', '')}|{entry.get('summary', '')}"
    return "sha1:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()


def _entry_content_html(entry: dict) -> str | None:
    content = entry.get("content")
    if content and isinstance(content, list) and content[0].get("value"):
        return content[0]["value"]
    return entry.get("summary")


def parse_feed(content: bytes, feed_lang_fallback: str | None = None) -> ParsedFeed:
    """Parse raw feed bytes into a normalised ParsedFeed (no network)."""
    parsed = feedparser.parse(content)
    feed = parsed.get("feed", {})
    feed_lang = feed.get("language") or feed_lang_fallback

    articles: list[ParsedArticle] = []
    for entry in parsed.get("entries", []):
        published = _struct_to_dt(entry.get("published_parsed") or entry.get("updated_parsed"))
        articles.append(
            ParsedArticle(
                guid=_entry_guid(entry),
                url=entry.get("link"),
                title=entry.get("title"),
                author=entry.get("author"),
                content_html=_entry_content_html(entry),
                summary=entry.get("summary"),
                lang=entry.get("language") or feed_lang,
                published_at=published,
            )
        )
    return ParsedFeed(
        title=feed.get("title"),
        site_url=feed.get("link"),
        lang=feed_lang,
        articles=articles,
    )


# --- Fetching (conditional GET) ---------------------------------------------


async def fetch_feed(client: httpx.AsyncClient, source: Source) -> FetchResult:
    headers = {"User-Agent": settings.user_agent, "Accept": "application/rss+xml, */*"}
    if source.etag:
        headers["If-None-Match"] = source.etag
    if source.last_modified:
        headers["If-Modified-Since"] = source.last_modified
    try:
        resp = await client.get(
            source.feed_url,
            headers=headers,
            follow_redirects=True,
            timeout=settings.http_timeout_s,
        )
    except httpx.HTTPError as exc:
        return FetchResult(status="error", error=f"request: {exc!s}")

    if resp.status_code == 304:
        return FetchResult(status="not_modified")
    if resp.status_code >= 400:
        return FetchResult(status="error", error=f"http {resp.status_code}")
    return FetchResult(
        status="ok",
        content=resp.content,
        etag=resp.headers.get("ETag"),
        last_modified=resp.headers.get("Last-Modified"),
    )


# --- Persistence -------------------------------------------------------------


async def store_articles(db: AsyncSession, source: Source, parsed: ParsedFeed) -> int:
    """Insert new articles, skipping duplicates by (source_id, guid).

    Returns the number of newly inserted rows.
    """
    if not parsed.articles:
        return 0

    incoming = {a.guid: a for a in parsed.articles}  # de-dup within the feed itself
    existing = await db.execute(
        select(Article.guid).where(Article.source_id == source.id, Article.guid.in_(list(incoming)))
    )
    known = set(existing.scalars().all())
    new = [a for guid, a in incoming.items() if guid not in known]
    if not new:
        return 0

    rows = [
        {
            "source_id": source.id,
            "guid": a.guid,
            "url": a.url,
            "title": a.title,
            "author": a.author,
            "content_html": a.content_html,
            "summary": a.summary,
            "lang": a.lang,
            "published_at": a.published_at,
        }
        for a in new
    ]
    # ON CONFLICT DO NOTHING guards against races with a second worker.
    stmt = (
        pg_insert(Article).values(rows).on_conflict_do_nothing(constraint="uq_articles_source_guid")
    )
    result = await db.execute(stmt)
    return result.rowcount or 0


# --- Scheduling / backoff ----------------------------------------------------


def compute_next_fetch(
    interval_s: int, error_count: int, *, now: datetime | None = None
) -> datetime:
    """Next poll time. Exponential backoff while error_count > 0, capped."""
    now = now or datetime.now(UTC)
    if error_count <= 0:
        delay = interval_s
    else:
        delay = min(interval_s * (2**error_count), settings.ingest_max_interval_s)
    return now + timedelta(seconds=delay)


async def refresh_source(
    db: AsyncSession, client: httpx.AsyncClient, source: Source
) -> FetchResult:
    """Fetch, parse, store, and reschedule a single source."""
    result = await fetch_feed(client, source)
    now = datetime.now(UTC)

    if result.status == "error":
        source.error_count += 1
        source.next_fetch_at = compute_next_fetch(
            source.fetch_interval_s, source.error_count, now=now
        )
        await db.commit()
        return result

    if result.status == "ok" and result.content is not None:
        parsed = parse_feed(result.content)
        await store_articles(db, source, parsed)
        if not source.title and parsed.title:
            source.title = parsed.title
        if not source.site_url and parsed.site_url:
            source.site_url = parsed.site_url
        source.etag = result.etag
        source.last_modified = result.last_modified

    # Success (ok or not_modified): clear errors and schedule normally.
    source.error_count = 0
    source.last_fetch_at = now
    source.next_fetch_at = compute_next_fetch(source.fetch_interval_s, 0, now=now)
    await db.commit()
    return result
