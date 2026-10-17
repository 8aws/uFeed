from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.fixture(autouse=True)
def _no_guest_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    # One shared client IP and a shared Redis: the limiter is tested on its own.
    monkeypatch.setattr(settings, "guest_max_per_ip_hour", 0)
    monkeypatch.setattr(settings, "guest_max_per_day", 0)


async def _guest(api: AsyncClient) -> tuple[dict, dict]:
    resp = await api.post("/api/auth/guest", json={"locale": "es"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    return body["user"], {"Authorization": f"Bearer {body['tokens']['access_token']}"}


async def test_guest_gets_an_account_without_personal_data(api: AsyncClient) -> None:
    user, headers = await _guest(api)
    assert user["is_guest"] is True
    assert user["role"] == "guest"
    assert user["locale"] == "es"
    assert user["email"].endswith("@guest.example.org")

    me = await api.get("/api/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["is_guest"] is True

    other, _ = await _guest(api)
    assert other["id"] != user["id"]
    assert other["email"] != user["email"]


async def test_guest_cannot_sign_in_by_email(api: AsyncClient) -> None:
    user, _ = await _guest(api)
    resp = await api.post("/api/auth/login", json={"email": user["email"], "password": "x" * 12})
    assert resp.status_code == 401


async def test_guest_plan_has_no_ai_and_no_keys(api: AsyncClient) -> None:
    _, headers = await _guest(api)
    keys = await api.post("/api/keys", headers=headers, json={"name": "k", "scopes": ["read"]})
    assert keys.status_code == 403
    assert keys.json()["error"]["code"].startswith("plan_limit")
    site = (await api.get("/api/site")).json()
    assert site["guest_access"] is True
    assert site["plan_limits"]["guest"]["ai_features"] is False
    assert site["plan_limits"]["guest"]["max_feeds"] == 20


async def test_guest_cannot_use_password_or_digest(api: AsyncClient) -> None:
    _, headers = await _guest(api)
    pwd = await api.post(
        "/api/me/password",
        headers=headers,
        json={"current_password": "x", "new_password": "newpassword1"},
    )
    assert pwd.status_code == 403
    assert pwd.json()["error"]["code"] == "guest_account"
    digest = await api.patch("/api/me", headers=headers, json={"digest_hour": 8})
    assert digest.status_code == 403
    # Other profile fields still work.
    ok = await api.patch("/api/me", headers=headers, json={"display_name": "Visitor"})
    assert ok.status_code == 200


async def test_upgrade_keeps_the_data_and_gives_a_real_account(api: AsyncClient) -> None:
    _, headers = await _guest(api)
    folder = await api.post("/api/folders", headers=headers, json={"name": "News"})
    assert folder.status_code == 201

    email = f"new-{uuid.uuid4().hex[:10]}@example.com"
    resp = await api.post(
        "/api/auth/upgrade", headers=headers, json={"email": email, "password": "supersecret1"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["email"] == email
    assert body["user"]["is_guest"] is False
    assert body["user"]["role"] == "free"
    new = {"Authorization": f"Bearer {body['tokens']['access_token']}"}

    folders = (await api.get("/api/folders", headers=new)).json()
    assert [f["name"] for f in folders] == ["News"]
    # The guest's old token no longer works; the new credentials do.
    assert (await api.get("/api/me", headers=headers)).status_code == 401
    login = await api.post("/api/auth/login", json={"email": email, "password": "supersecret1"})
    assert login.status_code == 200
    # And it is no longer a guest.
    again = await api.post(
        "/api/auth/upgrade", headers=new, json={"email": email, "password": "supersecret1"}
    )
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "not_guest"


async def test_upgrade_refuses_a_taken_email(api: AsyncClient) -> None:
    taken = f"taken-{uuid.uuid4().hex[:10]}@example.com"
    reg = await api.post("/api/auth/register", json={"email": taken, "password": "supersecret1"})
    assert reg.status_code == 201
    _, headers = await _guest(api)
    resp = await api.post(
        "/api/auth/upgrade", headers=headers, json={"email": taken, "password": "supersecret1"}
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken"


async def test_guest_can_delete_itself_without_a_password(api: AsyncClient) -> None:
    _, headers = await _guest(api)
    resp = await api.post("/api/me/delete", headers=headers, json={})
    assert resp.status_code == 200
    assert (await api.get("/api/me", headers=headers)).status_code == 401


async def test_guest_access_can_be_turned_off(
    api: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "guest_access", False)
    resp = await api.post("/api/auth/guest", json={})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "guest_disabled"
    assert (await api.get("/api/site")).json()["guest_access"] is False


async def test_guest_creation_is_limited_per_ip(
    api: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []

    async def fake_check(bucket: str, limit: int, window_s: int = 60) -> bool:
        seen.append(bucket)
        return not bucket.startswith("guest:127")

    monkeypatch.setattr("app.api.routes.auth.check_rate", fake_check)
    resp = await api.post("/api/auth/guest", json={})
    assert resp.status_code == 429
    assert seen and seen[0].startswith("guest:")


async def test_idle_guests_are_deleted_but_registered_users_are_not(
    api: AsyncClient, db_session
) -> None:
    from datetime import timedelta

    from sqlalchemy import select

    from app.models.user import User
    from app.services import moderation

    guest, _ = await _guest(api)
    email = f"keep-{uuid.uuid4().hex[:10]}@example.com"
    reg = await api.post("/api/auth/register", json={"email": email, "password": "supersecret1"})
    assert reg.status_code == 201
    old = moderation.now() - timedelta(days=45)
    for e in (guest["email"], email):
        row = (await db_session.execute(select(User).where(User.email == e))).scalar_one()
        row.created_at = old
        row.last_seen_at = old
    await db_session.commit()

    assert await moderation.delete_idle_guests(db_session, 30) >= 1
    left = (
        (
            await db_session.execute(
                select(User.email).where(User.email.in_([guest["email"], email]))
            )
        )
        .scalars()
        .all()
    )
    assert left == [email]
