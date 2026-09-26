from __future__ import annotations

from functools import lru_cache

import redis.asyncio as redis

from app.core.config import settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.from_url(settings.redis_url, decode_responses=True)


async def check_rate(bucket: str, limit: int, window_s: int = 60) -> bool:
    """Fixed-window limiter. Returns True if the call is allowed.

    Fails open: if Redis is unavailable, requests are allowed rather than
    taking the API down with the cache.
    """
    if limit <= 0:
        return True
    key = f"rl:{bucket}"
    try:
        client = get_redis()
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_s)
        return count <= limit
    except Exception:  # noqa: BLE001 - never let the limiter break the API
        return True


async def cooldown(bucket: str, seconds: int) -> int:
    """Allow one action per `seconds` for this bucket.

    Returns 0 if the action may proceed (and starts the cooldown), otherwise
    the seconds left to wait. Fails open like `check_rate`.
    """
    if seconds <= 0:
        return 0
    key = f"cd:{bucket}"
    try:
        client = get_redis()
        if await client.set(key, "1", ex=seconds, nx=True):
            return 0
        ttl = await client.ttl(key)
        return max(int(ttl), 1)
    except Exception:  # noqa: BLE001 - never let the limiter break the API
        return 0
