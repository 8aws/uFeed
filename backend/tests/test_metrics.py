from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import metrics
from tests.test_admin import _h, _register, _set_role


async def test_metrics_sample_and_series(api: AsyncClient, db_session: AsyncSession) -> None:
    await metrics.count("tts", 1500, 2048)
    await metrics.count("tts", 500)
    await metrics.count("mt", 3000)
    data = await metrics.sample(db_session)
    assert data["users"] >= 0 and "db_mb" in data and "tts_cache_mb" in data

    admin = await _register(api)
    await _set_role(db_session, admin.json()["user"]["id"], "admin")
    r = await api.get("/api/admin/metrics?days=7", headers=_h(admin))
    assert r.status_code == 200
    body = r.json()
    assert body["samples"] and "db_mb" in body["samples"][-1]
    today = body["daily"][-1]
    assert today["tts_n"] >= 2 and today["tts_ms"] >= 2000 and today["mt_n"] >= 1

    user = await _register(api)
    assert (await api.get("/api/admin/metrics", headers=_h(user))).status_code == 403
