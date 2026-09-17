from __future__ import annotations

import uuid

from app.core.ratelimit import check_rate


async def test_fixed_window_limits_after_threshold() -> None:
    bucket = f"test-{uuid.uuid4().hex}"
    results = [await check_rate(bucket, 3, window_s=60) for _ in range(5)]
    assert results == [True, True, True, False, False]


async def test_zero_limit_disables() -> None:
    assert await check_rate(f"test-{uuid.uuid4().hex}", 0) is True
