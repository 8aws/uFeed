from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.source import Source
from app.services.ai import dedup_pending, embed_pending, summarize_pending
from app.services.ingest import refresh_source

log = logging.getLogger("ufeed.ingest")


async def select_due_sources(db: AsyncSession, now: datetime, limit: int) -> list[Source]:
    """Active sources whose next_fetch_at has passed (or was never set)."""
    stmt = (
        select(Source)
        .where(
            Source.is_active.is_(True),
            or_(Source.next_fetch_at.is_(None), Source.next_fetch_at <= now),
        )
        .order_by(Source.next_fetch_at.nulls_first())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def run_tick() -> int:
    """Process one batch of due sources. Returns how many were processed."""
    now = datetime.now(UTC)
    processed = 0
    async with SessionLocal() as db:
        sources = await select_due_sources(db, now, settings.ingest_batch)
        async with httpx.AsyncClient() as client:
            for source in sources:
                try:
                    result = await refresh_source(db, client, source)
                    log.info("ingested %s -> %s", source.feed_url, result.status)
                except Exception:  # noqa: BLE001 - one bad feed must not kill the tick
                    await db.rollback()
                    log.exception("ingest failed for %s", source.feed_url)
                processed += 1
        # Embed + summarise newly-ingested articles (best-effort; no-op if AI down).
        try:
            embedded = await embed_pending(db)
            if embedded:
                log.info("embedded %d articles", embedded)
        except Exception:  # noqa: BLE001
            await db.rollback()
            log.exception("embedding pass failed")
        try:
            summarised = await summarize_pending(db)
            if summarised:
                log.info("summarised %d articles", summarised)
        except Exception:  # noqa: BLE001
            await db.rollback()
            log.exception("summary pass failed")
        try:
            deduped = await dedup_pending(db)
            if deduped:
                log.info("deduped %d articles", deduped)
        except Exception:  # noqa: BLE001
            await db.rollback()
            log.exception("dedup pass failed")
    return processed
