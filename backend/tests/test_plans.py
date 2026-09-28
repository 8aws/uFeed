from __future__ import annotations

import io
import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_admin import _h, _register, _set_role
from tests.test_reader import _seed_source

FREE = {"refresh_cooldown_s": 600, "max_feeds": 100, "max_api_keys": 1, "ai_features": True}


async def _admin_and_user(api: AsyncClient, db: AsyncSession) -> tuple[dict, dict]:
    admin = await _register(api)
    await _set_role(db, admin.json()["user"]["id"], "admin")
    user = await _register(api)
    await _set_role(db, user.json()["user"]["id"], "free")
    return _h(admin), _h(user)


async def _set_free(api: AsyncClient, admin: dict, **changes) -> None:
    r = await api.put("/api/admin/plans", headers=admin, json={"free": {**FREE, **changes}})
    assert r.status_code == 200, r.text


async def test_only_admins_edit_plans(api: AsyncClient, db_session: AsyncSession) -> None:
    admin, user = await _admin_and_user(api, db_session)
    assert (await api.put("/api/admin/plans", headers=user, json={"free": FREE})).status_code == 403
    bad = await api.put("/api/admin/plans", headers=admin, json={"free": {**FREE, "max_feeds": -1}})
    assert bad.status_code == 422
    await _set_free(api, admin, max_feeds=7)
    site = (await api.get("/api/site")).json()
    assert site["plan_limits"]["free"]["max_feeds"] == 7
    assert site["plan_limits"]["admin"]["max_feeds"] is None  # other plans untouched


async def test_feed_limit(api: AsyncClient, db_session: AsyncSession) -> None:
    admin, user = await _admin_and_user(api, db_session)
    await _set_free(api, admin, max_feeds=1)
    a = await _seed_source(db_session, [("a", "<p>a</p>")])
    b = await _seed_source(db_session, [("b", "<p>b</p>")])
    assert (
        await api.post("/api/sources", headers=user, json={"url": a.feed_url})
    ).status_code == 201
    over = await api.post("/api/sources", headers=user, json={"url": b.feed_url})
    assert over.status_code == 403 and over.json()["error"]["code"] == "plan_limit_feeds"

    opml = f"""<opml version="2.0"><body>
      <outline text="x" xmlUrl="https://opml-{uuid.uuid4().hex}.example/feed"/>
    </body></opml>""".encode()
    r = await api.post(
        "/api/opml/import", headers=user, files={"file": ("f.opml", io.BytesIO(opml))}
    )
    assert r.json() == {"imported": 0, "skipped": 1}


async def test_api_key_limit(api: AsyncClient, db_session: AsyncSession) -> None:
    _, user = await _admin_and_user(api, db_session)  # free default: 1 key
    assert (await api.post("/api/keys", headers=user, json={"name": "a"})).status_code == 201
    second = await api.post("/api/keys", headers=user, json={"name": "b"})
    assert second.status_code == 403 and second.json()["error"]["code"] == "plan_limit_keys"


async def test_ai_features_toggle(api: AsyncClient, db_session: AsyncSession) -> None:
    admin, user = await _admin_and_user(api, db_session)
    await _set_free(api, admin, ai_features=False)
    r = await api.get("/api/foryou", headers=user)
    assert r.status_code == 403 and r.json()["error"]["code"] == "plan_limit_ai"
    # Semantic search degrades to text search instead of failing.
    assert (await api.get("/api/articles?q=test&semantic=true", headers=user)).status_code == 200
    assert (await api.get(f"/api/articles/{uuid.uuid4()}/similar", headers=user)).json() == []


async def test_refresh_cooldown_is_editable(api: AsyncClient, db_session: AsyncSession) -> None:
    admin, user = await _admin_and_user(api, db_session)
    await _set_free(api, admin, refresh_cooldown_s=0)
    assert (await api.post("/api/refresh", headers=user)).status_code == 200
    assert (await api.post("/api/refresh", headers=user)).status_code == 200
