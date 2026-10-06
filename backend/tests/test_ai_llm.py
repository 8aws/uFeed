from __future__ import annotations

import os
import time
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ratelimit import get_redis
from app.models.article import Article
from app.services import ai as ai_service
from app.services import ai_queue, tts
from app.workers import ai_jobs
from tests.test_admin import _h, _register, _set_role
from tests.test_reader import _seed_source


async def _clear_queue() -> None:
    await get_redis().delete(ai_queue.PENDING, ai_queue.RUNNING)


@pytest.fixture(autouse=True)
async def _clean_queue(monkeypatch):
    """Each test starts with an empty AI queue, and never fetches web pages."""
    # The app shares one Redis client; each test runs in its own event loop.
    get_redis.cache_clear()
    await _clear_queue()

    async def no_fetch(db, article):
        return None

    monkeypatch.setattr(ai_jobs.fulltext, "fetch", no_fetch)
    yield
    await _clear_queue()


async def _reader(api: AsyncClient, db: AsyncSession, role: str) -> dict:
    r = await _register(api)
    await _set_role(db, r.json()["user"]["id"], role)
    return _h(r)


async def _articles(
    api: AsyncClient, db: AsyncSession, h: dict, n: int = 1, lang: str = "en"
) -> list[str]:
    src = await _seed_source(
        db, [(f"Soldier gets {70 + i} months", "<p>long english text</p>") for i in range(n)]
    )
    await db.execute(update(Article).where(Article.source_id == src.id).values(lang=lang))
    await db.commit()
    await api.post("/api/sources", headers=h, json={"url": src.feed_url})
    items = (await api.get("/api/articles", headers=h)).json()["items"]
    return [a["id"] for a in items if a["source_id"] == str(src.id)]


def _fake_llm(calls: list):
    async def fake(items):
        calls.extend(items)
        return [
            {"summary": f"Resumen {i}.", "title": "Soldado condenado", "model": "fake"}
            for i, _ in enumerate(items)
        ]

    return fake


async def _run_queue(db: AsyncSession) -> None:
    while jobs := await ai_queue.take(settings.ai_queue_batch):
        await ai_jobs.process(jobs, db)


async def test_queued_then_stored_for_everyone(
    api: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    calls: list = []
    monkeypatch.setattr(ai_service, "llm_summaries", _fake_llm(calls))
    h = await _reader(api, db_session, "general")
    [aid] = await _articles(api, db_session, h)

    empty = (await api.get(f"/api/articles/{aid}/ai-summary?lang=es", headers=h)).json()
    assert empty["summary"] is None and empty["status"] == "none"
    assert await ai_queue.pending_count() == 0  # nothing queued implicitly

    queued = await api.get(f"/api/articles/{aid}/ai-summary?lang=es&generate=true", headers=h)
    assert queued.status_code == 200, queued.text
    body = queued.json()
    assert body["status"] == "queued" and body["position"] == 1 and body["eta_s"] >= 1
    # Polling while queued doesn't queue it again.
    again = (await api.get(f"/api/articles/{aid}/ai-summary?lang=es", headers=h)).json()
    assert again["status"] == "queued" and await ai_queue.pending_count() == 1

    await _run_queue(db_session)
    assert calls[0]["lang"] == "es" and calls[0]["src_lang"] == "en"
    assert calls[0]["translate_title"] is True  # English article -> translated headline

    done = (await api.get(f"/api/articles/{aid}/ai-summary?lang=es", headers=h)).json()
    assert done["status"] == "ready" and done["summary"] == "Resumen 0."
    assert done["title"] == "Soldado condenado" and done["cached"] is True

    # Asking again (any reader) gets the stored one: no queue, no generation.
    got = await api.get(f"/api/articles/{aid}/ai-summary?lang=es&generate=true", headers=h)
    assert got.json()["status"] == "ready" and len(calls) == 1


async def test_same_language_keeps_title(
    api: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    calls: list = []
    monkeypatch.setattr(ai_service, "llm_summaries", _fake_llm(calls))
    h = await _reader(api, db_session, "general")
    [aid] = await _articles(api, db_session, h, lang="es-ES")
    await api.get(f"/api/articles/{aid}/ai-summary?lang=es&generate=true", headers=h)
    await _run_queue(db_session)
    assert calls[0]["translate_title"] is False


async def test_joining_a_queued_job(api: AsyncClient, db_session: AsyncSession) -> None:
    free = await _reader(api, db_session, "free")
    [a1, a2] = await _articles(api, db_session, free, n=2)
    r1 = await api.get(f"/api/articles/{a1}/ai-summary?lang=es&generate=true", headers=free)
    r2 = await api.get(f"/api/articles/{a2}/ai-summary?lang=es&generate=true", headers=free)
    assert (r1.json()["position"], r2.json()["position"]) == (1, 2)  # same plan: in order
    # A VIP asking for the second one joins that job and moves it to the front.
    status, created = await ai_queue.enqueue(uuid.UUID(a2), "es", 0)
    assert created is False and status["position"] == 1
    assert await ai_queue.pending_count() == 2


async def test_priority_order_between_plans(api: AsyncClient, db_session: AsyncSession) -> None:
    now = uuid.uuid4()
    await ai_queue.enqueue(now, "es", 2)  # free, first
    later = uuid.uuid4()
    await ai_queue.enqueue(later, "es", 0)  # VIP, after
    jobs = await ai_queue.take(1)
    assert jobs[0]["article_id"] == str(later)
    await ai_queue.finish(jobs[0], True)


async def test_free_daily_allowance(
    api: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(ai_service, "llm_summaries", _fake_llm([]))
    h = await _reader(api, db_session, "free")
    ids = await _articles(api, db_session, h, n=4)
    codes = [
        (await api.get(f"/api/articles/{a}/ai-summary?generate=true", headers=h)).status_code
        for a in ids
    ]
    assert codes == [200, 200, 200, 403]  # 3 new summaries a day on the free plan
    blocked = await api.get(f"/api/articles/{ids[3]}/ai-summary?generate=true", headers=h)
    assert blocked.json()["error"]["code"] == "plan_limit_ai_daily"
    # Summaries that already exist stay free to read.
    await _run_queue(db_session)
    ok = await api.get(f"/api/articles/{ids[0]}/ai-summary?generate=true", headers=h)
    assert ok.status_code == 200 and ok.json()["status"] == "ready"


async def test_guards(api: AsyncClient, db_session: AsyncSession, monkeypatch) -> None:
    async def down(items):
        return None

    monkeypatch.setattr(ai_service, "llm_summaries", down)
    h = await _reader(api, db_session, "general")
    [aid] = await _articles(api, db_session, h)
    await api.get(f"/api/articles/{aid}/ai-summary?generate=true", headers=h)
    await _run_queue(db_session)
    failed = (await api.get(f"/api/articles/{aid}/ai-summary", headers=h)).json()
    assert failed["status"] == "failed" and failed["error"] == "ai_unavailable"
    # Asking again retries.
    retry = await api.get(f"/api/articles/{aid}/ai-summary?generate=true", headers=h)
    assert retry.json()["status"] == "queued"

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
    [other] = await _articles(api, db_session, h)
    blocked = await api.get(f"/api/articles/{other}/ai-summary?generate=true", headers=h)
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "plan_limit_ai"


async def test_interrupted_jobs_go_back_to_the_queue() -> None:
    aid = uuid.uuid4()
    await ai_queue.enqueue(aid, "es", 1)
    await ai_queue.take(1)  # the worker dies while generating it
    assert await ai_queue.pending_count() == 0
    assert await ai_queue.requeue_running() == 1
    assert (await ai_queue.status(aid, "es"))["status"] == "queued"


async def test_voice_cache_follows_retention(
    db_session: AsyncSession, tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "tts_cache_dir", str(tmp_path))
    src = await _seed_source(db_session, [("A", "<p>x</p>")])
    art = (
        await db_session.execute(Article.__table__.select().where(Article.source_id == src.id))
    ).first()
    kept = tmp_path / f"{art.id}-esf-v1.mp3"
    stale = tmp_path / f"{uuid.uuid4()}-esf-v1.mp3"  # its article was purged
    old = tmp_path / f"{art.id}-esm-v1.mp3"
    for p in (kept, stale, old):
        p.write_bytes(b"mp3")
    gone = time.time() - 91 * 86400
    os.utime(old, (gone, gone))  # nobody has played it for 91 days
    out = await tts.purge_old(db_session, 90)
    assert kept.exists() and not stale.exists() and not old.exists()
    assert out["audio_deleted"] == 2
