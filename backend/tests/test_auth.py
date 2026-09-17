from __future__ import annotations

import uuid

from httpx import AsyncClient


def _email() -> str:
    return f"user-{uuid.uuid4().hex[:12]}@example.com"


async def _register(api: AsyncClient, password: str = "supersecret1") -> tuple[str, dict]:
    email = _email()
    resp = await api.post(
        "/api/auth/register",
        json={"email": email, "password": password, "locale": "es"},
    )
    assert resp.status_code == 201, resp.text
    return email, resp.json()


async def test_register_returns_user_and_tokens(api: AsyncClient) -> None:
    email, body = await _register(api)
    assert body["user"]["email"] == email
    assert body["user"]["locale"] == "es"
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]


async def test_register_duplicate_email_conflicts(api: AsyncClient) -> None:
    email, _ = await _register(api)
    resp = await api.post("/api/auth/register", json={"email": email, "password": "supersecret1"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken"


async def test_login_success_and_failure(api: AsyncClient) -> None:
    email, _ = await _register(api, password="rightpassword1")
    ok = await api.post("/api/auth/login", json={"email": email, "password": "rightpassword1"})
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = await api.post("/api/auth/login", json={"email": email, "password": "wrong"})
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "invalid_credentials"


async def test_me_requires_auth(api: AsyncClient) -> None:
    resp = await api.get("/api/me")
    assert resp.status_code == 401


async def test_me_and_patch_locale(api: AsyncClient) -> None:
    _, body = await _register(api)
    token = body["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me = await api.get("/api/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["locale"] == "es"

    patched = await api.patch(
        "/api/me", headers=headers, json={"locale": "en", "display_name": "Manu"}
    )
    assert patched.status_code == 200
    assert patched.json()["locale"] == "en"
    assert patched.json()["display_name"] == "Manu"


async def test_refresh_rotates_tokens(api: AsyncClient) -> None:
    _, body = await _register(api)
    refresh_token = body["tokens"]["refresh_token"]

    resp = await api.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert resp.json()["access_token"]

    # An access token must not be usable as a refresh token.
    access = body["tokens"]["access_token"]
    bad = await api.post("/api/auth/refresh", json={"refresh_token": access})
    assert bad.status_code == 401
