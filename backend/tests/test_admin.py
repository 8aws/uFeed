from __future__ import annotations

import uuid

from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from tests.test_reader import _seed_source


async def _register(api: AsyncClient, expect: int = 201) -> Response:
    r = await api.post(
        "/api/auth/register",
        json={"email": f"a-{uuid.uuid4().hex[:12]}@example.com", "password": "supersecret1"},
    )
    assert r.status_code == expect, r.text
    return r


def _h(r: Response) -> dict:
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


async def _set_role(db: AsyncSession, user_id: str, role: str) -> None:
    await db.execute(update(User).where(User.id == uuid.UUID(user_id)).values(role=role))
    await db.commit()


async def test_me_exposes_role(api: AsyncClient) -> None:
    r = await _register(api)
    me = await api.get("/api/me", headers=_h(r))
    assert me.status_code == 200
    assert me.json()["role"] in {"free", "general", "vip", "editor", "admin"}


async def test_admin_endpoints_require_admin(api: AsyncClient, db_session: AsyncSession) -> None:
    r = await _register(api)
    await _set_role(db_session, r.json()["user"]["id"], "vip")
    assert (await api.get("/api/admin/settings", headers=_h(r))).status_code == 403
    assert (await api.get("/api/admin/users", headers=_h(r))).status_code == 403


async def test_admin_can_close_registration(api: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _register(api)
    await _set_role(db_session, admin.json()["user"]["id"], "admin")
    h = _h(admin)

    r = await api.patch("/api/admin/settings", headers=h, json={"registration_open": False})
    assert r.status_code == 200, r.text
    assert r.json()["registration_open"] is False
    site = (await api.get("/api/site")).json()
    assert site["registration_open"] is False
    assert site["refresh_cooldown_s"]["free"] > 0

    closed = await _register(api, expect=403)
    assert closed.json()["error"]["code"] == "registration_closed"

    r = await api.patch(
        "/api/admin/settings", headers=h, json={"registration_open": True, "default_role": "vip"}
    )
    assert r.json()["default_role"] == "vip"
    newbie = await _register(api)
    assert newbie.json()["user"]["role"] == "vip"


async def test_admin_manages_users_but_not_self(api: AsyncClient, db_session: AsyncSession) -> None:
    admin = await _register(api)
    aid = admin.json()["user"]["id"]
    await _set_role(db_session, aid, "admin")
    other = await _register(api)
    oid = other.json()["user"]["id"]
    h = _h(admin)

    users = (await api.get("/api/admin/users", headers=h)).json()
    assert {aid, oid} <= {u["id"] for u in users}

    r = await api.patch(f"/api/admin/users/{oid}", headers=h, json={"role": "editor"})
    assert r.status_code == 200 and r.json()["role"] == "editor"

    # Disabling an account cuts its session.
    r = await api.patch(f"/api/admin/users/{oid}", headers=h, json={"is_active": False})
    assert r.json()["is_active"] is False
    assert (await api.get("/api/me", headers=_h(other))).status_code == 401

    # An admin can't lock themselves out.
    r = await api.patch(f"/api/admin/users/{aid}", headers=h, json={"role": "free"})
    assert r.status_code == 400
    r = await api.patch(f"/api/admin/users/{aid}", headers=h, json={"is_active": False})
    assert r.status_code == 400


async def test_refresh_cooldown_by_role(api: AsyncClient, db_session: AsyncSession) -> None:
    r = await _register(api)
    uid = r.json()["user"]["id"]
    h = _h(r)
    await _set_role(db_session, uid, "free")

    assert (await api.post("/api/refresh", headers=h)).status_code == 200
    again = await api.post("/api/refresh", headers=h)
    assert again.status_code == 429
    assert again.json()["error"]["code"] == "refresh_cooldown"
    assert int(again.headers["retry-after"]) > 0

    # Higher plans refresh immediately.
    await _set_role(db_session, uid, "vip")
    assert (await api.post("/api/refresh", headers=h)).status_code == 200


async def test_public_mark_read_respects_scopes(api: AsyncClient, db_session: AsyncSession) -> None:
    r = await _register(api)
    h = _h(r)
    src = await _seed_source(db_session, [("A", "<p>body a</p>")])
    sub = await api.post("/api/sources", headers=h, json={"url": src.feed_url})
    assert sub.status_code == 201, sub.text

    async def key(scopes: list[str]) -> dict:
        k = await api.post("/api/keys", headers=h, json={"name": "t", "scopes": scopes})
        return {"X-API-Key": k.json()["key"]}

    full, read_only, legacy = await key(["read", "state"]), await key(["read"]), await key([])

    items = (await api.get("/api/v1/articles?unread=true", headers=full)).json()["items"]
    aid = items[0]["id"]

    # A read-only key can list but not change state.
    denied = await api.post(f"/api/v1/articles/{aid}/read", headers=read_only)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "insufficient_scope"

    assert (await api.post(f"/api/v1/articles/{aid}/read", headers=full)).status_code == 200
    unread = (await api.get("/api/v1/articles?unread=true", headers=full)).json()["items"]
    assert all(i["id"] != aid for i in unread)

    # Undo, and keys without scopes stay full-access.
    assert (await api.delete(f"/api/v1/articles/{aid}/read", headers=legacy)).status_code == 200
    unread = (await api.get("/api/v1/articles?unread=true", headers=full)).json()["items"]
    assert any(i["id"] == aid for i in unread)

    missing = await api.post(f"/api/v1/articles/{uuid.uuid4()}/read", headers=full)
    assert missing.status_code == 404


async def test_public_save_and_favorite(api: AsyncClient, db_session: AsyncSession) -> None:
    r = await _register(api)
    h = _h(r)
    src = await _seed_source(db_session, [("A", "<p>a</p>"), ("B", "<p>b</p>")])
    await api.post("/api/sources", headers=h, json={"url": src.feed_url})
    k = await api.post("/api/keys", headers=h, json={"name": "t", "scopes": ["read", "state"]})
    key = {"X-API-Key": k.json()["key"]}
    ro = await api.post("/api/keys", headers=h, json={"name": "ro", "scopes": ["read"]})
    read_only = {"X-API-Key": ro.json()["key"]}
    aid = (await api.get("/api/v1/articles", headers=key)).json()["items"][0]["id"]

    for action, flag, param in (
        ("save", "is_saved", "saved"),
        ("favorite", "is_favorite", "favorite"),
    ):
        denied = await api.post(f"/api/v1/articles/{aid}/{action}", headers=read_only)
        assert denied.status_code == 403
        assert (await api.post(f"/api/v1/articles/{aid}/{action}", headers=key)).status_code == 200
        art = (await api.get(f"/api/v1/articles/{aid}", headers=key)).json()
        assert art[flag] is True
        listed = (await api.get(f"/api/v1/articles?{param}=true", headers=key)).json()["items"]
        assert [i["id"] for i in listed] == [aid]
        assert (
            await api.delete(f"/api/v1/articles/{aid}/{action}", headers=key)
        ).status_code == 200
        assert (await api.get(f"/api/v1/articles/{aid}", headers=key)).json()[flag] is False

    missing = await api.post(f"/api/v1/articles/{uuid.uuid4()}/favorite", headers=key)
    assert missing.status_code == 404
