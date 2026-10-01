from __future__ import annotations

import logging

import pytest
from httpx import AsyncClient

from tests.test_admin import _h, _register


async def test_diag_report_is_logged(api: AsyncClient, caplog: pytest.LogCaptureFixture) -> None:
    h = _h(await _register(api))
    report = {
        "context": {"reader": True, "article": "x"},
        "events": [{"k": "beat", "t": 1}, {"k": "lost", "t": 2, "target": "BUTTON Favorito"}],
    }
    with caplog.at_level(logging.WARNING, logger="ufeed.diag"):
        r = await api.post("/api/me/diag", headers=h, json=report)
    assert r.status_code == 200
    assert any("BUTTON Favorito" in rec.getMessage() for rec in caplog.records)


async def test_diag_requires_login_and_caps_size(api: AsyncClient) -> None:
    assert (await api.post("/api/me/diag", json={"events": []})).status_code == 401
    h = _h(await _register(api))
    r = await api.post("/api/me/diag", headers=h, json={"events": [{"k": "beat"}] * 500})
    assert r.status_code == 422
