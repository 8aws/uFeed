from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_admin import _h, _register, _set_role

PW = "supersecret1"


def _bearer(access: str) -> dict:
    return {"Authorization": f"Bearer {access}"}


async def _login(api: AsyncClient, email: str, password: str) -> int:
    r = await api.post("/api/auth/login", json={"email": email, "password": password})
    return r.status_code


async def test_change_password_rotates_sessions(api: AsyncClient) -> None:
    r = await _register(api)
    email = r.json()["user"]["email"]
    old = _h(r)
    old_refresh = r.json()["tokens"]["refresh_token"]

    bad = await api.post(
        "/api/me/password", headers=old, json={"current_password": "nope", "new_password": "x" * 8}
    )
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "wrong_password"

    ok = await api.post(
        "/api/me/password", headers=old, json={"current_password": PW, "new_password": "newsecret1"}
    )
    assert ok.status_code == 200, ok.text
    new = _bearer(ok.json()["access_token"])

    # Old sessions (access + refresh) stop working; the new one works.
    assert (await api.get("/api/me", headers=old)).status_code == 401
    assert (
        await api.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    ).status_code == 401
    assert (await api.get("/api/me", headers=new)).status_code == 200

    assert await _login(api, email, "newsecret1") == 200
    assert await _login(api, email, PW) == 401


async def test_admin_reset_password(api: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _register(api)
    await _set_role(db_session, admin.json()["user"]["id"], "admin")
    user = await _register(api)
    uid = user.json()["user"]["id"]
    email = user.json()["user"]["email"]

    # Only admins, and not on themselves.
    assert (
        await api.post(f"/api/admin/users/{uid}/reset-password", headers=_h(user))
    ).status_code == 403
    aid = admin.json()["user"]["id"]
    self_reset = await api.post(f"/api/admin/users/{aid}/reset-password", headers=_h(admin))
    assert self_reset.status_code == 400

    reset = await api.post(f"/api/admin/users/{uid}/reset-password", headers=_h(admin))
    assert reset.status_code == 200, reset.text
    temp = reset.json()["temporary_password"]
    assert len(temp) >= 8

    # The user's existing session is gone; the temporary password works...
    assert (await api.get("/api/me", headers=_h(user))).status_code == 401
    login = await api.post("/api/auth/login", json={"email": email, "password": temp})
    assert login.status_code == 200
    h = _bearer(login.json()["access_token"])
    assert (await api.get("/api/me", headers=h)).json()["must_change_password"] is True

    # ...and changing it clears the flag.
    changed = await api.post(
        "/api/me/password", headers=h, json={"current_password": temp, "new_password": "brandnew1"}
    )
    me = await api.get("/api/me", headers=_bearer(changed.json()["access_token"]))
    assert me.json()["must_change_password"] is False


async def test_reset_unknown_user(api: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _register(api)
    await _set_role(db_session, admin.json()["user"]["id"], "admin")
    r = await api.post(f"/api/admin/users/{uuid.uuid4()}/reset-password", headers=_h(admin))
    assert r.status_code == 404
