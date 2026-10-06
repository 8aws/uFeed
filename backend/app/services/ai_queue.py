"""Queue for AI summaries, served by plan priority.

A request doesn't wait for the model: it queues a job and gets back its
status (position, estimated wait), which the app polls. The worker runs the
queue in order of priority -- the plan's `ai_priority` (0 = VIP/editor/admin,
1 = general, 2 = free) and 3 for background pre-generation -- oldest first
within a priority, up to `ai_queue_batch` jobs at a time (the iGPU writes two
summaries together almost as fast as one).

A job is one article in one language, and the result is stored for everyone:
asking again, or another reader asking for the same summary, joins the job
already queued (and can only move it forward).
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from app.core.config import settings
from app.core.ratelimit import get_redis

log = logging.getLogger("ufeed.aiqueue")

PENDING = "aiq:pending"  # sorted set: job id -> priority * 1e13 + queued ms
RUNNING = "aiq:running"  # set of job ids being generated
AVG_MS = "aiq:avg_ms"  # running average of seconds per summary (ms)
JOB_TTL_S = 24 * 3600
BACKGROUND = 3
DEFAULT_MS = 12_000  # per summary when batched, before there's an average


def job_id(article_id: uuid.UUID | str, lang: str) -> str:
    return f"sum:{article_id}:{lang}"


def _key(jid: str) -> str:
    return f"aiq:job:{jid}"


def _score(priority: int, at_ms: int) -> float:
    return priority * 10**13 + at_ms


async def enqueue(
    article_id: uuid.UUID, lang: str, priority: int, user_id: uuid.UUID | None = None
) -> tuple[dict[str, Any], bool]:
    """Queue (or join) the summary job. Returns (status, created)."""
    r = get_redis()
    jid = job_id(article_id, lang)
    key = _key(jid)
    state = await r.hget(key, "status")
    if state in ("queued", "running"):
        if state == "queued":
            # Someone with a better plan asking moves it forward (LT: only lower).
            queued_at = int(await r.hget(key, "queued_ms") or time.time() * 1000)
            await r.zadd(PENDING, {jid: _score(priority, queued_at)}, lt=True)
        return await status(article_id, lang) or {"status": state}, False
    now = int(time.time() * 1000)
    await r.hset(
        key,
        mapping={
            "status": "queued",
            "article_id": str(article_id),
            "lang": lang,
            "priority": priority,
            "user_id": str(user_id or ""),
            "queued_ms": now,
            "error": "",
        },
    )
    await r.expire(key, JOB_TTL_S)
    await r.zadd(PENDING, {jid: _score(priority, now)})
    return await status(article_id, lang) or {"status": "queued"}, True


async def avg_ms() -> int:
    v = await get_redis().get(AVG_MS)
    return int(float(v)) if v else DEFAULT_MS


async def status(article_id: uuid.UUID, lang: str) -> dict[str, Any] | None:
    """Where the job is: queued (position, eta_s), running, failed; None if
    there's no job."""
    r = get_redis()
    jid = job_id(article_id, lang)
    job = await r.hgetall(_key(jid))
    if not job:
        return None
    state = job.get("status", "queued")
    out: dict[str, Any] = {"status": state}
    per = await avg_ms()
    batch = max(1, settings.ai_queue_batch)
    if state == "queued":
        rank = await r.zrank(PENDING, jid)
        if rank is None:  # being picked up right now
            out["status"] = "running"
        else:
            out["position"] = rank + 1
            running = await r.scard(RUNNING)
            # Jobs go `batch` at a time; each batch takes about per * batch.
            rounds = (rank + running) // batch + 1
            out["eta_s"] = max(1, round(rounds * per * batch / 1000))
    elif state == "running":
        started = int(job.get("started_ms") or 0)
        left = per * batch / 1000 - (time.time() * 1000 - started) / 1000 if started else 0
        out["eta_s"] = max(1, round(left))
    elif state == "failed":
        out["error"] = job.get("error") or "failed"
    return out


async def take(n: int) -> list[dict[str, Any]]:
    """Pop up to n jobs, best priority first, and mark them running."""
    r = get_redis()
    popped = await r.zpopmin(PENDING, n)
    jobs = []
    now = int(time.time() * 1000)
    for jid, _score_v in popped:
        key = _key(jid)
        job = await r.hgetall(key)
        if not job:
            continue
        await r.hset(key, mapping={"status": "running", "started_ms": now})
        await r.sadd(RUNNING, jid)
        jobs.append({**job, "id": jid})
    return jobs


async def finish(job: dict[str, Any], ok: bool, error: str = "", ms: int | None = None) -> None:
    """Done: the summary is stored (the job record goes); failed: kept a while
    so the reader sees why, then asking again retries."""
    r = get_redis()
    jid = job["id"]
    await r.srem(RUNNING, jid)
    if ok:
        await r.delete(_key(jid))
        if ms:
            prev = await avg_ms()
            await r.set(AVG_MS, int(prev * 0.7 + ms * 0.3))
    else:
        await r.hset(_key(jid), mapping={"status": "failed", "error": error[:200]})
        await r.expire(_key(jid), 600)


async def forget(article_id: uuid.UUID, lang: str) -> None:
    """Drop a failed job so the next request starts over."""
    await get_redis().delete(_key(job_id(article_id, lang)))


async def requeue_running() -> int:
    """After a worker restart: jobs it was generating go back to the queue."""
    r = get_redis()
    jids = await r.smembers(RUNNING)
    for jid in jids:
        job = await r.hgetall(_key(jid))
        await r.srem(RUNNING, jid)
        if job:
            await r.hset(_key(jid), "status", "queued")
            await r.zadd(
                PENDING,
                {jid: _score(int(job.get("priority") or 1), int(job.get("queued_ms") or 0))},
            )
    return len(jids)


async def pending_count() -> int:
    return int(await get_redis().zcard(PENDING))
