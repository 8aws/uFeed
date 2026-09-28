from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.source import Source
from app.services import source_health
from app.workers.scheduler import select_due_sources
from tests.test_admin import _h, _register, _set_role
from tests.test_reader import _seed_source


async def _subscribed(api: AsyncClient, db: AsyncSession, **fields) -> tuple[dict, Source]:
    h = _h(await _register(api))
    src = await _seed_source(db, [("A", "<p>a</p>")])
    await api.post("/api/sources", headers=h, json={"url": src.feed_url})
    await db.execute(update(Source).where(Source.id == src.id).values(**fields))
    await db.commit()
    await db.refresh(src)
    return h, src


async def test_user_health_statuses(api: AsyncClient, db_session: AsyncSession) -> None:
    h, src = await _subscribed(
        api,
        db_session,
        error_count=4,
        last_error="http 404",
        last_error_at=datetime.now(UTC),
        last_fetch_at=datetime.now(UTC) - timedelta(days=3),
    )
    rows = (await api.get("/api/sources/health", headers=h)).json()
    row = next(r for r in rows if r["source_id"] == str(src.id))
    assert row["status"] == "failing" and row["last_error"] == "http 404"

    await db_session.execute(
        update(Source)
        .where(Source.id == src.id)
        .values(error_count=0, last_error=None, last_fetch_at=datetime.now(UTC))
    )
    await db_session.commit()
    rows = (await api.get("/api/sources/health", headers=h)).json()
    # The seeded article is from 2025 -> no new posts for > 30 days.
    assert next(r for r in rows if r["source_id"] == str(src.id))["status"] == "stale"


async def test_editor_pause_resume_and_orphans(api: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _register(api)
    await _set_role(db_session, admin.json()["user"]["id"], "editor")
    ah = _h(admin)
    _, src = await _subscribed(api, db_session, error_count=5)

    listed = (await api.get("/api/curation/sources", headers=ah)).json()
    mine = next(r for r in listed if r["source_id"] == str(src.id))
    assert mine["subscribers"] == 1 and mine["status"] == "failing"

    r = await api.patch(f"/api/curation/sources/{src.id}", headers=ah, json={"paused": True})
    assert r.status_code == 200
    await db_session.refresh(src)
    assert src.is_active is False
    await api.patch(f"/api/curation/sources/{src.id}", headers=ah, json={"paused": False})
    await db_session.refresh(src)
    assert src.is_active is True and src.error_count == 0

    orphan = Source(feed_url=f"https://orphan.example/{uuid.uuid4().hex}.xml")
    db_session.add(orphan)
    await db_session.commit()
    oid = orphan.id
    deleted = (await api.post("/api/curation/sources/delete-orphans", headers=ah)).json()["deleted"]
    assert deleted >= 1
    assert await db_session.scalar(select(Source.id).where(Source.id == oid)) is None
    assert await db_session.scalar(select(Source.id).where(Source.id == src.id)) == src.id


async def test_scheduler_skips_unfollowed_feeds(db_session: AsyncSession) -> None:
    orphan = Source(feed_url=f"https://orphan.example/{uuid.uuid4().hex}.xml")
    db_session.add(orphan)
    await db_session.commit()
    due = await select_due_sources(db_session, datetime.now(UTC), 10_000)
    assert orphan.id not in {s.id for s in due}


def test_status_for_paused_and_pending() -> None:
    src = Source(feed_url="https://x.test/f", is_active=False, error_count=0)
    assert source_health.status_for(src, None) == "paused"
    src.is_active = True
    assert source_health.status_for(src, None) == "pending"


async def test_scheduler_polls_only_feeds_of_active_users(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    from app.models.user import User

    h, src = await _subscribed(api, db_session, next_fetch_at=None, error_count=0)
    me = (await api.get("/api/me", headers=h)).json()["id"]
    due = {s.id for s in await select_due_sources(db_session, datetime.now(UTC), 10_000)}
    assert src.id in due  # follower just used the app

    old = datetime.now(UTC) - timedelta(days=3)
    await db_session.execute(
        update(User).where(User.id == uuid.UUID(me)).values(last_seen_at=old, created_at=old)
    )
    await db_session.commit()
    due = {s.id for s in await select_due_sources(db_session, datetime.now(UTC), 10_000)}
    assert src.id not in due  # nobody active follows it -> not polled


async def test_sync_on_open(api: AsyncClient, db_session: AsyncSession) -> None:
    h, src = await _subscribed(api, db_session, next_fetch_at=None, error_count=0)
    first = await api.post("/api/sync", headers=h)
    assert first.status_code == 200, first.text
    # Due feeds were found and a refresh ran. (Its per-source sessions can't
    # see this test's uncommitted rows, so counts aren't asserted here.)
    assert first.json()["skipped"] is False
    again = await api.post("/api/sync", headers=h)
    assert again.json()["skipped"] is True  # per-user cooldown
