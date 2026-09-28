"""Changes made offline reach the server late: they keep their original time."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.read_event import ReadEvent
from tests.test_admin import _h, _register
from tests.test_reader import _seed_source, _subscribe


async def _setup(api: AsyncClient, db: AsyncSession, n: int = 2) -> tuple[dict, list[str]]:
    src = await _seed_source(db, [(f"T{i}", "<p>x</p>") for i in range(n)])
    h = _h(await _register(api))
    await _subscribe(api, h, src.feed_url)
    ids = [a["id"] for a in (await api.get("/api/articles", headers=h)).json()["items"]]
    return h, ids


async def _events(db: AsyncSession, article_id: str) -> list[ReadEvent]:
    rows = await db.execute(select(ReadEvent).where(ReadEvent.article_id == uuid.UUID(article_id)))
    return list(rows.scalars())


async def test_late_events_keep_their_time(api: AsyncClient, db_session: AsyncSession) -> None:
    h, (a, b) = await _setup(api, db_session)
    two_days = datetime.now(UTC) - timedelta(days=2)
    r = await api.post(
        f"/api/articles/{a}/read-event",
        headers=h,
        json={"dwell_ms": 30000, "completion": 0.8, "at": two_days.isoformat()},
    )
    assert r.status_code == 200
    r = await api.post(
        f"/api/articles/{a}/engage", headers=h, json={"kind": "open", "at": two_days.isoformat()}
    )
    assert r.status_code == 200
    evs = await _events(db_session, a)
    assert len(evs) == 2
    assert all(abs((e.created_at - two_days).total_seconds()) < 1 for e in evs)

    # Too old for any ranking: accepted (so the client stops retrying), not stored.
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()
    r = await api.post(f"/api/articles/{b}/read-event", headers=h, json={"at": old})
    assert r.status_code == 200 and await _events(db_session, b) == []
    # A clock in the future is clamped to now.
    future = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    await api.post(f"/api/articles/{b}/engage", headers=h, json={"kind": "skip", "at": future})
    (ev,) = await _events(db_session, b)
    assert ev.created_at <= datetime.now(UTC)


async def test_mark_all_read_before_cutoff(api: AsyncClient, db_session: AsyncSession) -> None:
    h, (a, b) = await _setup(api, db_session)
    now = datetime.now(UTC)
    await db_session.execute(
        update(Article)
        .where(Article.id == uuid.UUID(a))
        .values(fetched_at=now - timedelta(hours=2))
    )
    await db_session.execute(
        update(Article).where(Article.id == uuid.UUID(b)).values(fetched_at=now)
    )
    await db_session.commit()

    cutoff = (now - timedelta(hours=1)).isoformat()
    r = await api.post("/api/articles/mark-all-read", headers=h, json={"before": cutoff})
    assert r.status_code == 200
    unread = [
        x["id"] for x in (await api.get("/api/articles?unread=true", headers=h)).json()["items"]
    ]
    assert a not in unread and b in unread
