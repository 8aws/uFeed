from __future__ import annotations

import uuid

from httpx import AsyncClient

from app.core.security import parse_api_key_prefix


def test_parse_prefix_handles_underscores_in_secret() -> None:
    # base64url secrets can contain "_"; the prefix must still parse.
    assert parse_api_key_prefix("uf_abcd1234_se_cr_et") == "abcd1234"
    assert parse_api_key_prefix("not-a-key") is None


async def _auth_headers(api: AsyncClient) -> dict:
    resp = await api.post(
        "/api/auth/register",
        json={"email": f"k-{uuid.uuid4().hex[:12]}@example.com", "password": "supersecret1"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


async def test_create_list_and_revoke_key(api: AsyncClient) -> None:
    headers = await _auth_headers(api)

    created = await api.post("/api/keys", headers=headers, json={"name": "cli", "scopes": ["read"]})
    assert created.status_code == 201, created.text
    payload = created.json()
    assert payload["name"] == "cli"
    assert payload["key"].startswith("uf_")  # plaintext returned once
    key_id = payload["id"]

    listed = await api.get("/api/keys", headers=headers)
    assert listed.status_code == 200
    keys = listed.json()
    assert any(k["id"] == key_id for k in keys)
    assert "key" not in keys[0]  # secret never listed

    revoked = await api.delete(f"/api/keys/{key_id}", headers=headers)
    assert revoked.status_code == 200

    # Revoking twice fails.
    again = await api.delete(f"/api/keys/{key_id}", headers=headers)
    assert again.status_code == 404


async def test_public_api_requires_key(api: AsyncClient) -> None:
    # No key -> 401
    resp = await api.get("/api/v1/sources")
    assert resp.status_code == 401

    # Invalid key -> 401
    resp = await api.get("/api/v1/sources", headers={"X-API-Key": "uf_dead_beef"})
    assert resp.status_code == 401


async def test_valid_key_authorizes_public_api(api: AsyncClient) -> None:
    headers = await _auth_headers(api)
    created = await api.post("/api/keys", headers=headers, json={"name": "ext", "scopes": []})
    plaintext = created.json()["key"]

    # Valid key passes auth; data logic is WS3, so it reaches the 501 stub.
    resp = await api.get("/api/v1/sources", headers={"X-API-Key": plaintext})
    assert resp.status_code == 501
    assert resp.json()["error"]["code"] == "not_implemented"

    # A revoked key is rejected.
    key_id = created.json()["id"]
    await api.delete(f"/api/keys/{key_id}", headers=headers)
    resp = await api.get("/api/v1/sources", headers={"X-API-Key": plaintext})
    assert resp.status_code == 401
