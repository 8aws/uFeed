"""Runs the AI summary queue (see services/ai_queue) and, at night, queues
summaries ahead of time for the feeds VIP/editor/admin readers follow."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.article import Article
from app.models.article_ai import ArticleAI
from app.models.subscription import Subscription
from app.models.user import User
from app.services import ai as ai_service
from app.services import ai_queue, fulltext, metrics

log = logging.getLogger("ufeed.aiqueue")

SHORT_WORDS = 200  # below this a feed probably sent only an excerpt


async def process(jobs: list[dict], db: AsyncSession | None = None) -> None:
    """Generate one batch and store each summary for every reader. Every job
    taken ends finished (done or failed), even if something breaks."""
    if db is None:
        async with SessionLocal() as session:
            return await process(jobs, session)
    open_jobs = {job["id"]: job for job in jobs}

    async def close(job: dict, ok: bool, error: str = "", ms: int | None = None) -> None:
        open_jobs.pop(job["id"], None)
        await ai_queue.finish(job, ok, error, ms)

    try:
        items, ready = [], []
        for job in jobs:
            art = await db.get(Article, uuid.UUID(job["article_id"]))
            if art is None:
                await close(job, False, "article not found")
                continue
            if await db.get(ArticleAI, (art.id, job["lang"])) is not None:
                await close(job, True)  # someone else's job made it meanwhile
                continue
            # Summarise the whole article, not the feed's excerpt.
            if (art.word_count or 0) < SHORT_WORDS and art.full_status is None:
                await fulltext.fetch(db, art)
            src = (art.lang or "").split("-")[0].lower()
            items.append(
                {
                    "title": art.title or "",
                    "text": fulltext.body_html(art),
                    "lang": job["lang"],
                    "src_lang": src,
                    "translate_title": bool(src) and src != job["lang"],
                }
            )
            ready.append((job, art))
        if not ready:
            return
        t0 = time.monotonic()
        results = await ai_service.llm_summaries(items)
        per = int((time.monotonic() - t0) * 1000) // len(ready)
        if results is None:
            for job, _ in ready:
                await close(job, False, "ai_unavailable")
            return
        made = []
        for (job, art), out in zip(ready, results, strict=True):
            summary = (out.get("summary") or "").strip()
            if not summary:
                await close(job, False, "empty summary")
                continue
            await db.merge(
                ArticleAI(
                    article_id=art.id,
                    lang=job["lang"],
                    summary=summary,
                    title=out.get("title"),
                    model=out.get("model") or "llm",
                )
            )
            made.append(job)
        await db.commit()
        for job in made:
            await metrics.count("llm", per)
            await close(job, True, ms=per)
    finally:
        for job in list(open_jobs.values()):
            await ai_queue.finish(job, False, "internal error")


async def run_queue(stop: asyncio.Event | None = None) -> None:
    """Forever: take the best-placed jobs (a batch) and generate them."""
    n = await ai_queue.requeue_running()
    if n:
        log.info("requeued %d interrupted summaries", n)
    while not (stop and stop.is_set()):
        try:
            jobs = await ai_queue.take(settings.ai_queue_batch)
            if not jobs:
                await asyncio.sleep(1)
                continue
            await process(jobs)
        except Exception:  # noqa: BLE001 - keep serving the queue
            log.exception("AI queue batch failed")
            await asyncio.sleep(5)


async def pregenerate() -> int:
    """Queue (low priority) summaries of the last day's articles from feeds
    that VIP/editor/admin readers follow, in their languages, while the
    queue is idle. Returns how many were queued."""
    if settings.ai_pregen_per_run <= 0 or await ai_queue.pending_count():
        return 0
    since = datetime.now(UTC) - timedelta(days=1)
    active = datetime.now(UTC) - timedelta(days=14)
    async with SessionLocal() as db:
        readers = (
            await db.execute(
                select(User.id, User.locale).where(
                    User.role.in_(("vip", "editor", "admin")),
                    User.is_active.is_(True),
                    User.last_seen_at >= active,
                )
            )
        ).all()
        queued = 0
        for user_id, locale in readers:
            lang = (locale or "en")[:2]
            rows = (
                await db.execute(
                    select(Article.id)
                    .join(Subscription, Subscription.source_id == Article.source_id)
                    .where(
                        Subscription.user_id == user_id,
                        Article.fetched_at >= since,
                        ~exists().where(ArticleAI.article_id == Article.id, ArticleAI.lang == lang),
                    )
                    .order_by(Article.fetched_at.desc())
                    .limit(settings.ai_pregen_per_run - queued)
                )
            ).scalars()
            for article_id in rows:
                _, created = await ai_queue.enqueue(article_id, lang, ai_queue.BACKGROUND)
                queued += int(created)
            if queued >= settings.ai_pregen_per_run:
                break
    if queued:
        log.info("pre-generating %d summaries", queued)
    return queued
