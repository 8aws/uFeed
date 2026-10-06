"""Article retention: purge old articles so the database doesn't grow forever.

Never deleted: articles anyone saved or favourited, and the newest
KEEP_PER_SOURCE articles of each feed (so items still present in a live feed
aren't deleted and then re-ingested as "new"). Ingest also skips dated entries
older than the cutoff (see ingest.store_articles) for the same reason.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.article import Article
from app.models.article_state import ArticleState
from app.models.read_event import ReadEvent
from app.services import site as site_service
from app.services import tts as tts_service

log = logging.getLogger("ufeed.retention")

KEEP_PER_SOURCE = 50
BATCH = 2000
# Engagement events feed the trending/insights rankings (30-day window); keep
# them a while longer, then drop them.
EVENTS_MIN_DAYS = 60

# A duplicate group is shown through its "seed" (id == dup_group_id). If the
# seed was purged, promote the earliest remaining member so the rest stay visible.
_RESEED_ORPHAN_GROUPS = text("""
    WITH orphan AS (
        SELECT a.dup_group_id AS g,
               (array_agg(a.id ORDER BY a.fetched_at, a.id))[1] AS seed
        FROM articles a
        WHERE a.dup_group_id IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM articles s WHERE s.id = a.dup_group_id)
        GROUP BY a.dup_group_id
    )
    UPDATE articles a SET dup_group_id = o.seed FROM orphan o WHERE a.dup_group_id = o.g
    """)


def cutoff_for(days: int) -> datetime | None:
    """Oldest publication date kept, or None when retention is off (0 days)."""
    return datetime.now(UTC) - timedelta(days=days) if days > 0 else None


async def keep_horizon(
    db: AsyncSession, source_id: Any, incoming: list[datetime]
) -> datetime | None:
    """Date of the KEEP_PER_SOURCE-th newest article of a feed, counting what
    is stored plus what is about to be ingested (None if the feed is smaller).

    Mirrors the purge rule so ingest never adds something the next purge would
    delete: an entry is skipped only if it's older than the retention cutoff
    *and* older than this horizon.
    """
    age = func.coalesce(Article.published_at, Article.fetched_at)
    stored = (
        await db.execute(
            select(age)
            .where(Article.source_id == source_id)
            .order_by(age.desc())
            .limit(KEEP_PER_SOURCE)
        )
    ).scalars()
    dates = sorted([*stored, *incoming], reverse=True)
    return dates[KEEP_PER_SOURCE - 1] if len(dates) >= KEEP_PER_SOURCE else None


async def purge(db: AsyncSession, days: int) -> dict[str, Any]:
    cutoff = cutoff_for(days)
    if cutoff is None:
        return {"deleted_articles": 0, "deleted_events": 0}

    age = func.coalesce(Article.published_at, Article.fetched_at)
    ranked = select(
        Article.id.label("id"),
        age.label("age"),
        func.row_number().over(partition_by=Article.source_id, order_by=age.desc()).label("rn"),
    ).subquery()
    kept = select(ArticleState.article_id).where(
        or_(ArticleState.is_saved.is_(True), ArticleState.is_favorite.is_(True))
    )
    candidates = (
        select(ranked.c.id)
        .where(ranked.c.rn > KEEP_PER_SOURCE, ranked.c.age < cutoff, ranked.c.id.not_in(kept))
        .limit(BATCH)
    )

    deleted = 0
    while ids := list((await db.execute(candidates)).scalars().all()):
        await db.execute(delete(Article).where(Article.id.in_(ids)))
        await db.commit()
        deleted += len(ids)
    if deleted:
        await db.execute(_RESEED_ORPHAN_GROUPS)
        await db.commit()

    events_cutoff = datetime.now(UTC) - timedelta(days=max(days, EVENTS_MIN_DAYS))
    events = await db.execute(delete(ReadEvent).where(ReadEvent.created_at < events_cutoff))
    await db.commit()
    return {"deleted_articles": deleted, "deleted_events": events.rowcount or 0}


async def run_retention(db: AsyncSession | None = None) -> dict[str, Any]:
    """Purge with the configured window and record the outcome for the admin."""
    if db is None:
        async with SessionLocal() as session:
            return await run_retention(session)
    cfg = await site_service.get_settings(db)
    days = int(cfg["retention_days"])
    result = await purge(db, days)
    try:
        result.update(await tts_service.purge_old(db, days))
    except Exception:  # noqa: BLE001 - the article purge already happened
        log.exception("voice cache purge failed")
    result.update({"days": days, "at": datetime.now(UTC).isoformat()})
    await site_service.set_internal(db, "last_purge", result)
    log.info("retention (%sd): %s", days, result)
    return result
