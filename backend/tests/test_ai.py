from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.article import Article
from app.models.source import Source
from app.services import ai as ai_service


def _unit(i: int, dim: int = 384) -> list[float]:
    v = [0.0] * dim
    v[i] = 1.0
    return v


async def _register(api: AsyncClient) -> tuple[dict, str]:
    email = f"ai-{uuid.uuid4().hex[:12]}@example.com"
    r = await api.post("/api/auth/register", json={"email": email, "password": "supersecret1"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}, email


async def _seed_with_vectors(db: AsyncSession) -> tuple[Source, list[uuid.UUID]]:
    src = Source(feed_url=f"https://ex.com/{uuid.uuid4().hex}.xml", title="Seed")
    db.add(src)
    await db.flush()
    # two "python" articles (e0) and one "rust" article (e1)
    specs = [("Python A", _unit(0)), ("Python B", _unit(0)), ("Rust C", _unit(1))]
    ids = []
    for i, (title, vec) in enumerate(specs):
        art = Article(
            source_id=src.id, guid=f"{src.id}-{i}", title=title, content_html="x", embedding=vec
        )
        db.add(art)
        await db.flush()
        ids.append(art.id)
    await db.commit()
    return src, ids


async def test_embed_texts_fail_open_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_enabled", False)
    assert await ai_service.embed_texts(["hello"]) is None


async def test_similar_articles(api: AsyncClient, db_session: AsyncSession) -> None:
    headers, _ = await _register(api)
    src, ids = await _seed_with_vectors(db_session)
    await api.post("/api/sources", headers=headers, json={"url": src.feed_url})
    py_a, py_b, rust_c = ids

    resp = await api.get(f"/api/articles/{py_a}/similar", headers=headers)
    assert resp.status_code == 200
    order = [a["id"] for a in resp.json()]
    # The other python article ranks before the rust one.
    assert order.index(str(py_b)) < order.index(str(rust_c))


async def test_for_you_matches_taste(api: AsyncClient, db_session: AsyncSession) -> None:
    headers, _ = await _register(api)
    src, ids = await _seed_with_vectors(db_session)
    await api.post("/api/sources", headers=headers, json={"url": src.feed_url})
    py_a, py_b, rust_c = ids

    # Engage with a python article -> profile leans python.
    await api.post(f"/api/articles/{py_a}/save", headers=headers)

    resp = await api.get("/api/foryou", headers=headers)
    assert resp.status_code == 200
    recs = [a["id"] for a in resp.json()]
    # py_b (unread python) should be recommended above the rust one.
    assert recs.index(str(py_b)) < recs.index(str(rust_c))
