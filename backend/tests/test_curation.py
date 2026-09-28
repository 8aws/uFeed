from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.test_admin import _h, _register, _set_role
from tests.test_reader import _seed_source, _subscribe

SECTION = {
    "id": "tech",
    "name_en": "Technology",
    "name_es": "Tecnología",
    "feeds": [{"title": "Example", "url": "https://example.com/feed.xml", "lang": "en"}],
}


async def _user_with_role(api: AsyncClient, db: AsyncSession, role: str) -> dict:
    r = await _register(api)
    await _set_role(db, r.json()["user"]["id"], role)
    return _h(r)


async def test_curation_requires_editor(api: AsyncClient, db_session: AsyncSession) -> None:
    for role in ("free", "vip"):
        h = await _user_with_role(api, db_session, role)
        assert (await api.get("/api/curation/sources", headers=h)).status_code == 403
        r = await api.put("/api/curation/catalog", headers=h, json={"sections": [SECTION]})
        assert r.status_code == 403
    # Editors curate but can't manage the instance.
    eh = await _user_with_role(api, db_session, "editor")
    assert (await api.get("/api/curation/sources", headers=eh)).status_code == 200
    assert (await api.get("/api/admin/users", headers=eh)).status_code == 403
    assert (await api.get("/api/admin/settings", headers=eh)).status_code == 403


async def test_catalog_roundtrip(api: AsyncClient, db_session: AsyncSession) -> None:
    eh = await _user_with_role(api, db_session, "editor")
    uh = await _user_with_role(api, db_session, "free")

    r = await api.put("/api/curation/catalog", headers=eh, json={"sections": [SECTION]})
    assert r.status_code == 200 and r.json()["updated_at"]
    got = (await api.get("/api/catalog", headers=uh)).json()
    assert got["sections"][0]["feeds"][0]["url"] == "https://example.com/feed.xml"

    # Only http(s) URLs, known languages and unique section ids are accepted.
    bad_url = {**SECTION, "feeds": [{**SECTION["feeds"][0], "url": "javascript:alert(1)"}]}
    bad_lang = {**SECTION, "feeds": [{**SECTION["feeds"][0], "lang": "fr"}]}
    for sections in ([bad_url], [bad_lang], [SECTION, SECTION]):
        r = await api.put("/api/curation/catalog", headers=eh, json={"sections": sections})
        assert r.status_code == 422

    # None restores the app's built-in list.
    await api.put("/api/curation/catalog", headers=eh, json={"sections": None})
    assert (await api.get("/api/catalog", headers=uh)).json()["sections"] is None


async def test_hidden_article_leaves_shared_rankings(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    src = await _seed_source(db_session, [("Hot", "<p>x</p>"), ("Other", "<p>y</p>")])
    a = await _user_with_role(api, db_session, "free")
    await _subscribe(api, a, src.feed_url)
    items = (await api.get("/api/articles", headers=a)).json()["items"]
    hot = items[0]["id"]
    await api.post(
        f"/api/articles/{hot}/read-event", headers=a, json={"dwell_ms": 40000, "completion": 0.9}
    )
    ids = [t["article"]["id"] for t in (await api.get("/api/trending?limit=30", headers=a)).json()]
    assert hot in ids

    eh = await _user_with_role(api, db_session, "editor")
    r = await api.put(f"/api/curation/articles/{hot}/hidden", headers=eh, json={"hidden": True})
    assert r.status_code == 200
    ids = [t["article"]["id"] for t in (await api.get("/api/trending?limit=30", headers=a)).json()]
    assert hot not in ids
    ins = (await api.get("/api/insights", headers=a)).json()
    assert all(r["article"]["id"] != hot for lst in ins.values() for r in lst)
    # Still readable in the user's own feed.
    assert any(i["id"] == hot for i in (await api.get("/api/articles", headers=a)).json()["items"])
    hidden = (await api.get("/api/curation/hidden", headers=eh)).json()
    assert hidden[0]["article"]["id"] == hot
    assert (await api.get("/api/curation/hidden/ids", headers=eh)).json()["ids"] == [hot]

    await api.put(f"/api/curation/articles/{hot}/hidden", headers=eh, json={"hidden": False})
    ids = [t["article"]["id"] for t in (await api.get("/api/trending?limit=30", headers=a)).json()]
    assert hot in ids
