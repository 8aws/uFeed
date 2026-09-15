from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.workers.scheduler import run_tick

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ufeed.worker")


async def main() -> None:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_tick,
        "interval",
        seconds=settings.ingest_tick_s,
        max_instances=1,
        coalesce=True,
        next_run_time=None,
    )
    scheduler.start()
    log.info("ingestion worker started (tick=%ss)", settings.ingest_tick_s)

    # Run one tick immediately, then let the scheduler take over.
    await run_tick()

    stop = asyncio.Event()
    try:
        await stop.wait()
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
