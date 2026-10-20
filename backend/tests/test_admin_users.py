from __future__ import annotations

import uuid
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ban import Ban
from app.models.user import User
from app.services import auth as auth_service
from app.services import moderation


async def _admin(api: AsyncClient, db: AsyncSession) -> dict:
    r = await api.post(
        "/api/auth/register",
        json={"email": f"adm-{uuid.uuid4().hex[:10]}@example.com", "password": "supersecret1"},
    )
    uid = r.json()["user"]["id"]
    user = await db.get(User, uuid.UUID(uid))
    user.role = "admin"
    await db.commit()
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


async def _user(db: AsyncSession, tag: str, **fields) -> User:
    email = f"{tag}-{uuid.uuid4().hex[:8]}@example.com"
    u = await auth_service.create_user(db, email, "supersecret1", "es")
    for k, v in fields.items():
        setattr(u, k, v)
    await db.commit()
    return u


async def _guest(db: AsyncSession, **fields) -> User:
    g = await auth_service.create_guest(db, "es")
    for k, v in fields.items():
        setattr(g, k, v)
    await db.commit()
    return g


def _ids(page: dict) -> set[str]:
    return {u["id"] for u in page["items"]}


async def test_guests_are_hidden_unless_asked_for(api: AsyncClient, db_session: AsyncSession):
    h = await _admin(api, db_session)
    reg = await _user(db_session, "reg")
    g = await _guest(db_session)

    shown = (await api.get("/api/admin/users?limit=100", headers=h)).json()
    assert str(reg.id) in _ids(shown) and str(g.id) not in _ids(shown)
    only = (await api.get("/api/admin/users?guests=only&limit=100", headers=h)).json()
    assert str(g.id) in _ids(only) and str(reg.id) not in _ids(only)
    assert only["items"][0]["is_guest"] is True
    both = (await api.get("/api/admin/users?guests=all&limit=100", headers=h)).json()
    assert {str(reg.id), str(g.id)} <= _ids(both)


async def test_search_filters_and_paging(api: AsyncClient, db_session: AsyncSession):
    h = await _admin(api, db_session)
    tag = uuid.uuid4().hex[:8]
    a = await _user(db_session, f"zz{tag}-a", display_name="Ana Zeta")
    b = await _user(db_session, f"zz{tag}-b", role="vip")
    c = await _user(db_session, f"zz{tag}-c", is_active=False)

    found = (await api.get(f"/api/admin/users?q=zz{tag}&limit=100", headers=h)).json()
    assert found["total"] == 3 and _ids(found) == {str(a.id), str(b.id), str(c.id)}
    by_name = (await api.get("/api/admin/users?q=Ana%20Zeta", headers=h)).json()
    assert str(a.id) in _ids(by_name)

    vip = (await api.get(f"/api/admin/users?q=zz{tag}&role=vip", headers=h)).json()
    assert _ids(vip) == {str(b.id)}
    off = (await api.get(f"/api/admin/users?q=zz{tag}&status=disabled", headers=h)).json()
    assert _ids(off) == {str(c.id)}
    live = (await api.get(f"/api/admin/users?q=zz{tag}&status=active", headers=h)).json()
    assert _ids(live) == {str(a.id), str(b.id)}

    first = (
        await api.get(f"/api/admin/users?q=zz{tag}&limit=2&sort=email&order=asc", headers=h)
    ).json()
    second = (
        await api.get(
            f"/api/admin/users?q=zz{tag}&limit=2&offset=2&sort=email&order=asc", headers=h
        )
    ).json()
    assert first["total"] == second["total"] == 3
    assert len(first["items"]) == 2 and len(second["items"]) == 1
    emails = [u["email"] for u in first["items"] + second["items"]]
    assert emails == sorted(emails)


async def test_status_suspended_banned_dormant_and_inactive(
    api: AsyncClient, db_session: AsyncSession
):
    h = await _admin(api, db_session)
    tag = uuid.uuid4().hex[:8]
    now = moderation.now()
    sus = await _user(db_session, f"qq{tag}-s", suspended_until=now + timedelta(days=3))
    dor = await _user(db_session, f"qq{tag}-d", dormant_since=now - timedelta(days=2))
    ban = await _user(db_session, f"qq{tag}-b")
    db_session.add(Ban(email=ban.email, reason="spam", until=None))
    old = await _user(db_session, f"qq{tag}-o", last_seen_at=now - timedelta(days=100))
    old.created_at = now - timedelta(days=200)
    await db_session.commit()

    def q(extra: str) -> str:
        return f"/api/admin/users?q=qq{tag}&limit=100&{extra}"

    assert _ids((await api.get(q("status=suspended"), headers=h)).json()) == {str(sus.id)}
    assert _ids((await api.get(q("status=dormant"), headers=h)).json()) == {str(dor.id)}
    assert _ids((await api.get(q("status=banned"), headers=h)).json()) == {str(ban.id)}
    quiet = _ids((await api.get(q("inactive_days=60"), headers=h)).json())
    assert str(old.id) in quiet and str(sus.id) not in quiet
    active = _ids((await api.get(q("status=active"), headers=h)).json())
    assert active == {str(old.id)}  # the rest are suspended, dormant or banned


async def test_summary_counts_the_user_base(api: AsyncClient, db_session: AsyncSession):
    h = await _admin(api, db_session)
    before = (await api.get("/api/admin/users/summary", headers=h)).json()

    await _user(db_session, "new")
    await _user(db_session, "vip", role="vip")
    await _guest(db_session)
    await _guest(
        db_session,
        created_at=moderation.now() - timedelta(days=40),
        last_seen_at=moderation.now() - timedelta(days=40),
    )

    after = (await api.get("/api/admin/users/summary", headers=h)).json()
    assert after["users"] == before["users"] + 2
    assert after["new_7d"] == before["new_7d"] + 2
    assert after["by_role"].get("vip", 0) == before["by_role"].get("vip", 0) + 1
    assert after["guests"] == before["guests"] + 2
    assert after["guests_today"] == before["guests_today"] + 1
    assert after["guests_7d"] == before["guests_7d"] + 1
    assert after["guests_idle_30d"] == before["guests_idle_30d"] + 1
    assert after["guest_daily_cap"] == settings.guest_max_per_day


async def test_purge_guests_removes_only_idle_guests(api: AsyncClient, db_session: AsyncSession):
    h = await _admin(api, db_session)
    long_ago = moderation.now() - timedelta(days=60)
    idle = await _guest(db_session, created_at=long_ago, last_seen_at=long_ago)
    fresh = await _guest(db_session)
    reg = await _user(db_session, "keep", created_at=long_ago, last_seen_at=long_ago)

    res = await api.post("/api/admin/guests/purge", headers=h, json={"days": 30})
    assert res.status_code == 200 and res.json()["deleted"] >= 1
    left = (
        (await db_session.execute(select(User.id).where(User.id.in_([idle.id, fresh.id, reg.id]))))
        .scalars()
        .all()
    )
    assert set(left) == {fresh.id, reg.id}
    assert (
        await api.post("/api/admin/guests/purge", headers=h, json={"days": 0})
    ).status_code == 422


async def test_only_admins_see_the_list_and_summary(api: AsyncClient, db_session: AsyncSession):
    r = await api.post(
        "/api/auth/register",
        json={"email": f"u-{uuid.uuid4().hex[:8]}@example.com", "password": "supersecret1"},
    )
    h = {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}
    for path in ("/api/admin/users", "/api/admin/users/summary"):
        assert (await api.get(path, headers=h)).status_code == 403
    assert (await api.post("/api/admin/guests/purge", headers=h, json={})).status_code == 403
