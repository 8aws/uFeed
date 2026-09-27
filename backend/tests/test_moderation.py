from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.user import User
from app.services import moderation
from tests.test_admin import _h, _set_role

PW = "supersecret1"


async def _register(api: AsyncClient, email: str | None = None, expect: int = 201):
    email = email or f"m-{uuid.uuid4().hex[:12]}@example.com"
    r = await api.post("/api/auth/register", json={"email": email, "password": PW})
    assert r.status_code == expect, r.text
    return r


async def _login(api: AsyncClient, email: str):
    return await api.post("/api/auth/login", json={"email": email, "password": PW})


async def _admin(api: AsyncClient, db: AsyncSession) -> dict:
    r = await _register(api)
    await _set_role(db, r.json()["user"]["id"], "admin")
    return _h(r)


async def test_suspend_and_lift(api: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _admin(api, db_session)
    u = await _register(api)
    uid, email = u.json()["user"]["id"], u.json()["user"]["email"]

    r = await api.post(f"/api/admin/users/{uid}/suspend", headers=admin, json={"days": 7})
    assert r.status_code == 200 and r.json()["suspended_until"]
    assert (await api.get("/api/me", headers=_h(u))).status_code == 401
    denied = await _login(api, email)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "account_suspended"

    assert (await api.delete(f"/api/admin/users/{uid}/suspend", headers=admin)).status_code == 200
    assert (await _login(api, email)).status_code == 200


async def test_ban_blocks_account_and_reregistration(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await _admin(api, db_session)
    u = await _register(api)
    uid, email = u.json()["user"]["id"], u.json()["user"]["email"]

    # Permanent ban: account disabled...
    r = await api.post(f"/api/admin/users/{uid}/ban", headers=admin, json={"reason": "spam"})
    assert r.status_code == 200 and r.json()["banned"] is True and r.json()["ban_until"] is None
    assert (await _login(api, email)).json()["error"]["code"] == "account_disabled"

    # ...and after deleting it, the email can't sign up again.
    assert (await api.delete(f"/api/admin/users/{uid}", headers=admin)).status_code == 200
    again = await _register(api, email, expect=403)
    assert again.json()["error"]["code"] == "registration_banned"

    # Lifting the ban allows signing up again.
    bans = (await api.get("/api/admin/bans", headers=admin)).json()
    ban_id = next(b["id"] for b in bans if b["email"] == email)
    assert (await api.delete(f"/api/admin/bans/{ban_id}", headers=admin)).status_code == 200
    await _register(api, email)


async def test_temporary_ban_and_email_only_ban(api: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _admin(api, db_session)
    u = await _register(api)
    uid, email = u.json()["user"]["id"], u.json()["user"]["email"]

    r = await api.post(f"/api/admin/users/{uid}/ban", headers=admin, json={"days": 30})
    assert r.json()["ban_until"] is not None
    assert (await _login(api, email)).json()["error"]["code"] == "account_suspended"
    r = await api.delete(f"/api/admin/users/{uid}/ban", headers=admin)
    assert r.json()["banned"] is False
    assert (await _login(api, email)).status_code == 200

    # An email with no account can be banned up front.
    stranger = f"s-{uuid.uuid4().hex[:8]}@example.com"
    made = await api.post("/api/admin/bans", headers=admin, json={"email": stranger, "days": 7})
    assert made.status_code == 201
    assert (await _register(api, stranger, expect=403)).json()["error"]["code"] == (
        "registration_banned"
    )


async def test_admin_guards(api: AsyncClient, db_session: AsyncSession) -> None:
    admin_r = await _register(api)
    aid = admin_r.json()["user"]["id"]
    await _set_role(db_session, aid, "admin")
    admin = _h(admin_r)
    other = await _register(api)
    oid = other.json()["user"]["id"]
    await _set_role(db_session, oid, "admin")

    assert (await api.delete(f"/api/admin/users/{aid}", headers=admin)).status_code == 400
    assert (
        await api.post(f"/api/admin/users/{aid}/suspend", headers=admin, json={"days": 1})
    ).status_code == 400
    deleting_admin = await api.delete(f"/api/admin/users/{oid}", headers=admin)
    assert deleting_admin.json()["error"]["code"] == "cannot_delete_admin"
    # Non-admins can't moderate.
    plain = await _register(api)
    await _set_role(db_session, plain.json()["user"]["id"], "free")
    assert (
        await api.post(f"/api/admin/users/{oid}/suspend", headers=_h(plain), json={"days": 1})
    ).status_code == 403


async def test_suspended_owner_api_key_rejected(api: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _admin(api, db_session)
    u = await _register(api)
    key = (await api.post("/api/keys", headers=_h(u), json={"name": "k", "scopes": []})).json()
    hk = {"X-API-Key": key["key"]}
    assert (await api.get("/api/v1/sources", headers=hk)).status_code == 200
    uid = u.json()["user"]["id"]
    await api.post(f"/api/admin/users/{uid}/suspend", headers=admin, json={"days": 1})
    assert (await api.get("/api/v1/sources", headers=hk)).status_code == 401


async def test_activity_is_recorded(api: AsyncClient, db_session: AsyncSession) -> None:
    u = await _register(api)
    uid = uuid.UUID(u.json()["user"]["id"])
    old = datetime.now(UTC) - timedelta(days=10)
    await db_session.execute(update(User).where(User.id == uid).values(last_seen_at=old))
    await db_session.commit()
    assert (await api.get("/api/me", headers=_h(u))).status_code == 200
    seen = await db_session.scalar(select(User.last_seen_at).where(User.id == uid))
    assert seen > old + timedelta(days=9)


async def test_inactive_accounts_are_purged(api: AsyncClient, db_session: AsyncSession) -> None:
    old = datetime.now(UTC) - timedelta(days=400)

    async def make(role: str, key_used_recently: bool = False) -> uuid.UUID:
        r = await _register(api)
        uid = uuid.UUID(r.json()["user"]["id"])
        await db_session.execute(
            update(User).where(User.id == uid).values(role=role, created_at=old, last_seen_at=old)
        )
        if key_used_recently:
            k = await api.post("/api/keys", headers=_h(r), json={"name": "k", "scopes": []})
            await db_session.execute(
                update(ApiKey)
                .where(ApiKey.id == uuid.UUID(k.json()["id"]))
                .values(last_used_at=datetime.now(UTC))
            )
        await db_session.commit()
        return uid

    idle = await make("free")
    idle_admin = await make("admin")
    uses_api = await make("general", key_used_recently=True)

    removed = await moderation.purge_inactive(db_session, 180)
    ids = set(
        (await db_session.execute(select(User.id).where(User.id.in_([idle, idle_admin, uses_api]))))
        .scalars()
        .all()
    )
    assert idle not in ids and len(removed) >= 1
    assert idle_admin in ids  # admins are never auto-deleted
    assert uses_api in ids  # API-key use counts as activity
    assert await moderation.purge_inactive(db_session, 0) == []
