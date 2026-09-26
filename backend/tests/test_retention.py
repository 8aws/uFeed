from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.source import Source
from app.services import retention
from app.services.ingest import ParsedArticle, ParsedFeed, store_articles
from tests.test_admin import _h, _register, _set_role


async def _source(db: AsyncSession, ages_days: list[int]) -> tuple[Source, list[Article]]:
    now = datetime.now(UTC)
    src = Source(feed_url=f"https://ret.example/{uuid.uuid4().hex}.xml", title="Ret")
    db.add(src)
    await db.flush()
    arts = [
        Article(
            source_id=src.id,
            guid=f"{src.id}-{i}",
            title=f"a{i}",
            published_at=now - timedelta(days=d),
        )
        for i, d in enumerate(ages_days)
    ]
    db.add_all(arts)
    await db.commit()
    return src, arts


async def _count(db: AsyncSession, source_id: uuid.UUID) -> int:
    return int(
        await db.scalar(
            select(func.count()).select_from(Article).where(Article.source_id == source_id)
        )
    )


async def test_purge_keeps_newest_per_feed_and_saved(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    # 55 old articles: the newest 50 are always kept; the 5 oldest are candidates.
    src, arts = await _source(db_session, list(range(200, 255)))
    saved = arts[52]  # one of the 5 candidates

    r = await _register(api)
    await api.post("/api/sources", headers=_h(r), json={"url": src.feed_url})
    assert (await api.post(f"/api/articles/{saved.id}/save", headers=_h(r))).status_code == 200

    result = await retention.purge(db_session, 90)
    assert result["deleted_articles"] >= 4
    assert await _count(db_session, src.id) == 51
    assert await db_session.scalar(select(Article.id).where(Article.id == saved.id)) == saved.id


async def test_purge_off_when_zero_days(db_session: AsyncSession) -> None:
    src, _ = await _source(db_session, list(range(300, 360)))
    assert (await retention.purge(db_session, 0))["deleted_articles"] == 0
    assert await _count(db_session, src.id) == 60


async def test_purge_reseeds_orphaned_duplicate_groups(db_session: AsyncSession) -> None:
    # Seed A is the 51st newest of its feed and old -> purged; its duplicate B
    # (another feed, recent) must become its own seed so it stays visible.
    _, arts = await _source(db_session, [*range(1, 51), 200])
    seed = arts[-1]
    _, (dup,) = await _source(db_session, [1])
    seed.dup_group_id = seed.id
    dup.dup_group_id = seed.id
    await db_session.commit()

    await retention.purge(db_session, 90)
    assert await db_session.scalar(select(Article.id).where(Article.id == seed.id)) is None
    group = await db_session.scalar(select(Article.dup_group_id).where(Article.id == dup.id))
    assert group == dup.id


async def test_ingest_skips_entries_older_than_retention(db_session: AsyncSession) -> None:
    src = Source(feed_url=f"https://ret.example/{uuid.uuid4().hex}.xml")
    db_session.add(src)
    await db_session.commit()
    now = datetime.now(UTC)

    def entry(guid: str, published: datetime | None) -> ParsedArticle:
        return ParsedArticle(
            guid=guid,
            url=None,
            title=guid,
            author=None,
            content_html=None,
            summary=None,
            lang=None,
            published_at=published,
        )

    feed = ParsedFeed(
        title="t",
        site_url=None,
        lang=None,
        articles=[
            entry("old", now - timedelta(days=400)),
            entry("new", now),
            entry("undated", None),
        ],
    )
    assert await store_articles(db_session, src, feed) == 2  # default window: 90 days


async def test_admin_maintenance_and_run(api: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _register(api)
    await _set_role(db_session, admin.json()["user"]["id"], "admin")
    h = _h(admin)

    m = await api.get("/api/admin/maintenance", headers=h)
    assert m.status_code == 200, m.text
    assert m.json()["retention_days"] == 90
    assert m.json()["db_size_bytes"] > 0

    assert (
        await api.patch("/api/admin/settings", headers=h, json={"retention_days": -1})
    ).status_code == 422
    s = await api.patch("/api/admin/settings", headers=h, json={"retention_days": 30})
    assert s.json()["retention_days"] == 30

    run = await api.post("/api/admin/retention/run", headers=h)
    assert run.status_code == 200
    assert run.json()["last_purge"]["days"] == 30
