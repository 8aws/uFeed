from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.source import Source


async def _register(api: AsyncClient) -> dict:
    r = await api.post(
        "/api/auth/register",
        json={"email": f"a-{uuid.uuid4().hex[:12]}@example.com", "password": "supersecret1"},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


async def _seed(db: AsyncSession, n: int = 2) -> Source:
    src = Source(feed_url=f"https://ex.com/{uuid.uuid4().hex}.xml", title="Seed")
    db.add(src)
    await db.flush()
    for i in range(n):
        db.add(
            Article(
                source_id=src.id,
                guid=f"{src.id}-{i}",
                title=f"post {i}",
                content_html=f"body {i}",
                word_count=100 + i,
                published_at=datetime(2025, 1, i + 1, tzinfo=UTC),
            )
        )
    await db.commit()
    return src


async def _subscribe(api: AsyncClient, headers: dict, feed_url: str) -> None:
    r = await api.post("/api/sources", headers=headers, json={"url": feed_url})
    assert r.status_code == 201, r.text


async def test_favorite_is_separate_from_saved(api: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _register(api)
    src = await _seed(db_session)
    await _subscribe(api, headers, src.feed_url)

    items = (await api.get("/api/articles", headers=headers)).json()["items"]
    aid = items[0]["id"]
    assert items[0]["word_count"] in (100, 101)  # exposed to the client

    assert (await api.post(f"/api/articles/{aid}/favorite", headers=headers)).status_code == 200
    fav = (await api.get("/api/articles?favorite=true", headers=headers)).json()["items"]
    assert [a["id"] for a in fav] == [aid]
    # Favoriting does not save.
    saved = (await api.get("/api/articles?saved=true", headers=headers)).json()["items"]
    assert saved == []

    assert (await api.delete(f"/api/articles/{aid}/favorite", headers=headers)).status_code == 200
    assert (await api.get("/api/articles?favorite=true", headers=headers)).json()["items"] == []


async def test_read_events_feed_trending(api: AsyncClient, db_session: AsyncSession) -> None:
    src = await _seed(db_session, n=2)
    a = await _register(api)
    b = await _register(api)
    await _subscribe(api, a, src.feed_url)
    await _subscribe(api, b, src.feed_url)

    items = (await api.get("/api/articles", headers=a)).json()["items"]
    hot, cold = items[0]["id"], items[1]["id"]

    # Two distinct readers spend real time on `hot`, one skims `cold`.
    for h in (a, b):
        r = await api.post(
            f"/api/articles/{hot}/read-event",
            headers=h,
            json={"dwell_ms": 40000, "completion": 0.9},
        )
        assert r.status_code == 200
    await api.post(
        f"/api/articles/{cold}/read-event", headers=a, json={"dwell_ms": 1000, "completion": 0.1}
    )

    trending = (await api.get("/api/trending?window_hours=48", headers=a)).json()
    assert len(trending) >= 1
    top = trending[0]
    assert top["article"]["id"] == hot
    assert top["readers"] == 2
    assert top["score"] >= trending[-1]["score"]


async def test_read_event_requires_subscription(api: AsyncClient, db_session: AsyncSession) -> None:
    src = await _seed(db_session, n=1)
    headers = await _register(api)  # not subscribed
    from sqlalchemy import select

    aid = (
        await db_session.execute(select(Article.id).where(Article.source_id == src.id))
    ).scalar_one()
    r = await api.post(
        f"/api/articles/{aid}/read-event",
        headers=headers,
        json={"dwell_ms": 5000, "completion": 1.0},
    )
    assert r.status_code == 404
