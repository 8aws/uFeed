from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.services import ai as ai_service
from tests.test_admin import _h, _register, _set_role
from tests.test_reader import _seed_source


async def _article(api: AsyncClient, db: AsyncSession, lang: str = "en") -> tuple[dict, str, str]:
    r = await _register(api)
    await _set_role(db, r.json()["user"]["id"], "general")
    h = _h(r)
    src = await _seed_source(db, [("Soldier gets 70 months", "<p>long english text</p>")])
    await db.execute(update(Article).where(Article.source_id == src.id).values(lang=lang))
    await db.commit()
    await api.post("/api/sources", headers=h, json={"url": src.feed_url})
    aid = (await api.get("/api/articles", headers=h)).json()["items"][0]["id"]
    return h, aid, r.json()["user"]["id"]


async def test_generate_then_cached(
    api: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    calls: list[tuple] = []

    async def fake(title, text, lang, translate_title):
        calls.append((title, lang, translate_title))
        return {"summary": "Resumen en español.", "title": "Soldado condenado", "model": "fake"}

    monkeypatch.setattr(ai_service, "llm_summary", fake)
    h, aid, _ = await _article(api, db_session, lang="en")

    empty = (await api.get(f"/api/articles/{aid}/ai-summary?lang=es", headers=h)).json()
    assert empty["summary"] is None and calls == []  # nothing generated implicitly

    made = await api.get(f"/api/articles/{aid}/ai-summary?lang=es&generate=true", headers=h)
    assert made.status_code == 200, made.text
    assert made.json()["summary"] == "Resumen en español." and made.json()["cached"] is False
    assert calls == [("Soldier gets 70 months", "es", True)]  # English article -> translate title

    again = (await api.get(f"/api/articles/{aid}/ai-summary?lang=es", headers=h)).json()
    assert again["cached"] is True and again["title"] == "Soldado condenado"
    assert len(calls) == 1  # served from storage, not regenerated


async def test_same_language_does_not_translate_title(
    api: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    seen = {}

    async def fake(title, text, lang, translate_title):
        seen["t"] = translate_title
        return {"summary": "ok", "title": None, "model": "fake"}

    monkeypatch.setattr(ai_service, "llm_summary", fake)
    h, aid, _ = await _article(api, db_session, lang="es-ES")
    await api.get(f"/api/articles/{aid}/ai-summary?lang=es&generate=true", headers=h)
    assert seen["t"] is False


async def test_guards(api: AsyncClient, db_session: AsyncSession, monkeypatch) -> None:
    async def down(*_a, **_k):
        return None

    monkeypatch.setattr(ai_service, "llm_summary", down)
    h, aid, uid = await _article(api, db_session)
    r = await api.get(f"/api/articles/{aid}/ai-summary?generate=true", headers=h)
    assert r.status_code == 503 and r.json()["error"]["code"] == "ai_unavailable"

    missing = await api.get(f"/api/articles/{uuid.uuid4()}/ai-summary", headers=h)
    assert missing.status_code == 404

    admin = await _register(api)
    await _set_role(db_session, admin.json()["user"]["id"], "admin")
    plans = (await api.get("/api/site")).json()["plan_limits"]
    await api.put(
        "/api/admin/plans",
        headers=_h(admin),
        json={"general": {**plans["general"], "ai_features": False}},
    )
    blocked = await api.get(f"/api/articles/{aid}/ai-summary?generate=true", headers=h)
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "plan_limit_ai"
