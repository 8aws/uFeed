"""Resource monitor for the admin panel.

- count(): heavy work as it happens (voice, translation, AI summary), kept in
  a per-day Redis hash; never fails the caller.
- sample(): run by the worker every 15 min. Stores a snapshot (host load and
  memory, AI service memory, storage, users) and rolls today's counters into
  usage_daily, so the history survives Redis restarts.
Containers see the host's /proc/loadavg and /proc/meminfo, so no Docker
socket (or extra privilege) is needed.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ratelimit import get_redis
from app.models.article import Article
from app.models.metric import MetricSample, UsageDaily
from app.models.user import User

KINDS = ("tts", "mt", "llm")  # voice, translation, AI summary
KEEP_DAYS = 180


def _day_key(day: date) -> str:
    return f"stats:{day.isoformat()}"


async def count(kind: str, ms: int, size: int = 0) -> None:
    """Record one piece of heavy work (fails open)."""
    try:
        r = get_redis()
        key = _day_key(datetime.now(UTC).date())
        pipe = r.pipeline()
        pipe.hincrby(key, f"{kind}_n", 1)
        pipe.hincrby(key, f"{kind}_ms", int(ms))
        if size:
            pipe.hincrby(key, f"{kind}_bytes", int(size))
        pipe.expire(key, 4 * 86400)
        await pipe.execute()
    except Exception:  # noqa: BLE001 - metrics must never break the feature
        pass


def _host() -> dict:
    out: dict = {"cpus": os.cpu_count() or 0}
    try:
        load = Path("/proc/loadavg").read_text().split()
        out.update(load1=float(load[0]), load5=float(load[1]), load15=float(load[2]))
    except (OSError, ValueError, IndexError):
        pass
    try:
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = line.partition(":")
            info[k] = int(v.split()[0])  # kB
        total, avail = info["MemTotal"], info["MemAvailable"]
        out.update(mem_total_mb=total // 1024, mem_used_mb=(total - avail) // 1024)
    except (OSError, KeyError, ValueError):
        pass
    return out


async def _ai() -> dict:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            h = (await client.get(f"{settings.ai_url}/health")).json()
        return {"ai_rss_mb": h.get("rss_mb"), "ai_ok": True}
    except (httpx.HTTPError, ValueError):
        return {"ai_ok": False}


def _dir_mb(path: str) -> float:
    try:
        return round(sum(p.stat().st_size for p in Path(path).glob("*")) / 1048576, 1)
    except OSError:
        return 0.0


async def sample(db: AsyncSession) -> dict:
    now = datetime.now(UTC)
    data = _host() | await _ai()
    data["db_mb"] = round(
        int(await db.scalar(text("SELECT pg_database_size(current_database())")) or 0) / 1048576,
        1,
    )
    data["tts_cache_mb"] = _dir_mb(settings.tts_cache_dir)
    data["users"] = int(await db.scalar(select(func.count()).select_from(User)) or 0)
    for label, hours in (("active_24h", 24), ("active_7d", 168)):
        data[label] = int(
            await db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.last_seen_at >= now - timedelta(hours=hours))
            )
            or 0
        )
    data["articles"] = int(await db.scalar(select(func.count()).select_from(Article)) or 0)
    db.add(MetricSample(ts=now, data=data))
    # Roll the day's counters (today, and yesterday once more to close it).
    for day in (now.date(), now.date() - timedelta(days=1)):
        try:
            raw = await get_redis().hgetall(_day_key(day))
        except Exception:  # noqa: BLE001
            raw = {}
        if raw:
            usage = {k: int(v) for k, v in raw.items()}
            await db.execute(
                pg_insert(UsageDaily)
                .values(day=day, data=usage)
                .on_conflict_do_update(index_elements=["day"], set_={"data": usage})
            )
    await db.execute(delete(MetricSample).where(MetricSample.ts < now - timedelta(days=KEEP_DAYS)))
    await db.commit()
    return data


async def series(db: AsyncSession, days: int) -> dict:
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        await db.execute(
            select(MetricSample.ts, MetricSample.data)
            .where(MetricSample.ts >= since)
            .order_by(MetricSample.ts)
        )
    ).all()
    # Keep charts light: at most ~300 points.
    step = max(1, len(rows) // 300)
    samples = [{"ts": ts.isoformat(), **d} for ts, d in rows[::step]]
    if rows and rows[-1] is not rows[::step][-1]:
        samples.append({"ts": rows[-1][0].isoformat(), **rows[-1][1]})
    daily = (
        await db.execute(
            select(UsageDaily.day, UsageDaily.data)
            .where(UsageDaily.day >= since.date())
            .order_by(UsageDaily.day)
        )
    ).all()
    # Today live from Redis (the worker rolls it up every 15 min).
    today = datetime.now(UTC).date()
    try:
        live = {k: int(v) for k, v in (await get_redis().hgetall(_day_key(today))).items()}
    except Exception:  # noqa: BLE001
        live = {}
    days_out = {d.isoformat(): data for d, data in daily}
    if live:
        days_out[today.isoformat()] = live
    return {
        "samples": samples,
        "daily": [{"day": k, **v} for k, v in sorted(days_out.items())],
        "now": _host(),
    }
