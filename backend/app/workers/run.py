from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.db.session import SessionLocal
from app.services import metrics
from app.services.moderation import run_inactivity_cleanup
from app.services.retention import run_retention
from app.workers.scheduler import run_tick

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ufeed.worker")


async def _sample() -> None:
    try:
        async with SessionLocal() as db:
            await metrics.sample(db)
    except Exception:  # noqa: BLE001 - never stop the worker for a metric
        log.exception("metrics sample failed")


async def main() -> None:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_tick,
        "interval",
        seconds=settings.ingest_tick_s,
        max_instances=1,
        coalesce=True,
    )
    # Daily retention purge (UTC), before the 04:30 local backup.
    scheduler.add_job(run_retention, "cron", hour=2, minute=15, max_instances=1, coalesce=True)
    # Daily removal of accounts idle past the configured window (UTC).
    scheduler.add_job(
        run_inactivity_cleanup, "cron", hour=2, minute=30, max_instances=1, coalesce=True
    )
    # Resource monitor snapshot for the admin panel.
    scheduler.add_job(_sample, "interval", minutes=15, max_instances=1, coalesce=True)
    scheduler.start()
    log.info("ingestion worker started (tick=%ss)", settings.ingest_tick_s)

    # Run one tick immediately, then let the scheduler take over.
    await _sample()
    await run_tick()

    stop = asyncio.Event()
    try:
        await stop.wait()
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
