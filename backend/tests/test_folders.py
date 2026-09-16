from __future__ import annotations

import uuid

from httpx import AsyncClient


async def _headers(api: AsyncClient) -> dict:
    r = await api.post(
        "/api/auth/register",
        json={"email": f"f-{uuid.uuid4().hex[:12]}@example.com", "password": "supersecret1"},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


async def test_folders_crud_and_isolation(api: AsyncClient) -> None:
    a = await _headers(api)
    b = await _headers(api)

    created = await api.post("/api/folders", headers=a, json={"name": "News"})
    assert created.status_code == 201
    fid = created.json()["id"]

    listed = await api.get("/api/folders", headers=a)
    assert [f["name"] for f in listed.json()] == ["News"]

    # Another user cannot see or modify it.
    assert (await api.get("/api/folders", headers=b)).json() == []
    assert (
        await api.patch(f"/api/folders/{fid}", headers=b, json={"name": "x"})
    ).status_code == 404
    assert (await api.delete(f"/api/folders/{fid}", headers=b)).status_code == 404

    patched = await api.patch(
        f"/api/folders/{fid}", headers=a, json={"name": "Tech", "position": 2}
    )
    assert patched.json()["name"] == "Tech"
    assert patched.json()["position"] == 2

    assert (await api.delete(f"/api/folders/{fid}", headers=a)).status_code == 200
    assert (await api.get("/api/folders", headers=a)).json() == []
