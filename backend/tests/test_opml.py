from __future__ import annotations

import uuid

from httpx import AsyncClient


async def _register(api: AsyncClient) -> dict:
    r = await api.post(
        "/api/auth/register",
        json={"email": f"o-{uuid.uuid4().hex[:12]}@example.com", "password": "supersecret1"},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


async def test_opml_export_import_roundtrip(api: AsyncClient) -> None:
    a = await _register(api)

    # A: a folder with one feed, plus one root feed.
    folder = (await api.post("/api/folders", headers=a, json={"name": "Tech"})).json()
    feed_a = f"https://a-{uuid.uuid4().hex[:8]}.example/feed.xml"
    feed_b = f"https://b-{uuid.uuid4().hex[:8]}.example/feed.xml"
    assert (
        await api.post("/api/sources", headers=a, json={"url": feed_a, "folder_id": folder["id"]})
    ).status_code == 201
    assert (await api.post("/api/sources", headers=a, json={"url": feed_b})).status_code == 201

    exported = await api.get("/api/opml/export", headers=a)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/xml")
    xml = exported.text
    assert feed_a in xml and feed_b in xml and "Tech" in xml

    # B: import A's OPML.
    b = await _register(api)
    files = {"file": ("ufeed.opml", xml.encode(), "application/xml")}
    res = await api.post("/api/opml/import", headers=b, files=files)
    assert res.status_code == 200
    assert res.json() == {"imported": 2, "skipped": 0}

    # B now has both subscriptions and the "Tech" folder.
    b_sources = (await api.get("/api/sources", headers=b)).json()
    assert {s["source"]["feed_url"] for s in b_sources} == {feed_a, feed_b}
    b_folders = (await api.get("/api/folders", headers=b)).json()
    assert "Tech" in [f["name"] for f in b_folders]

    # Re-importing skips everything (idempotent; sources reused).
    res2 = await api.post("/api/opml/import", headers=b, files=files)
    assert res2.json() == {"imported": 0, "skipped": 2}
