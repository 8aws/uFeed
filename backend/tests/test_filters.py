from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from tests.test_admin import _h, _register
from tests.test_reader import _seed_source


async def _setup(api: AsyncClient, db: AsyncSession):
    h = _h(await _register(api))
    src = await _seed_source(
        db,
        [
            ("Bitcoin hits a new high", "<p>markets</p>"),
            ("Python 3.14 released", "<p>language</p>"),
            ("Crypto crash", "<p>bitcoin drops 50%</p>"),
        ],
    )
    # Muting matches title + summary (like real feeds), not the full body.
    await db.execute(
        update(Article).where(Article.source_id == src.id).values(summary=Article.content_html)
    )
    await db.commit()
    sub = (await api.post("/api/sources", headers=h, json={"url": src.feed_url})).json()
    return h, src, sub


async def _titles(api: AsyncClient, h: dict, query: str = "") -> list[str]:
    items = (await api.get(f"/api/articles?limit=50{query}", headers=h)).json()["items"]
    return sorted(i["title"] for i in items)


async def test_muted_keywords_hide_articles_and_counts(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    h, src, _ = await _setup(api, db_session)
    assert len(await _titles(api, h)) == 3

    r = await api.post("/api/filters/keywords", headers=h, json={"keyword": "  BitCoin "})
    assert r.status_code == 201 and r.json()["keyword"] == "bitcoin"
    # Title or summary match; case-insensitive.
    assert await _titles(api, h) == ["Python 3.14 released"]
    subs = (await api.get("/api/sources", headers=h)).json()
    assert next(s for s in subs if s["source"]["id"] == str(src.id))["unread_count"] == 1

    # Saved articles are never filtered.
    all_items = (await api.get("/api/articles?limit=50&saved=false", headers=h)).json()["items"]
    assert len(all_items) == 1
    kid = r.json()["id"]
    assert (await api.delete(f"/api/filters/keywords/{kid}", headers=h)).status_code == 200
    assert len(await _titles(api, h)) == 3


async def test_keyword_wildcards_are_literal(api: AsyncClient, db_session: AsyncSession) -> None:
    h, _, _ = await _setup(api, db_session)
    await api.post("/api/filters/keywords", headers=h, json={"keyword": "%"})
    # "%" must not match everything: only the article containing a literal %.
    assert await _titles(api, h) == ["Bitcoin hits a new high", "Python 3.14 released"]


async def test_saved_survive_mutes(api: AsyncClient, db_session: AsyncSession) -> None:
    h, _, _ = await _setup(api, db_session)
    items = (await api.get("/api/articles?limit=50", headers=h)).json()["items"]
    btc = next(i for i in items if i["title"].startswith("Bitcoin"))
    await api.post(f"/api/articles/{btc['id']}/save", headers=h)
    await api.post("/api/filters/keywords", headers=h, json={"keyword": "bitcoin"})
    saved = (await api.get("/api/articles?saved=true", headers=h)).json()["items"]
    assert [i["id"] for i in saved] == [btc["id"]]


async def test_muted_source_only_shows_when_opened(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    h, src, sub = await _setup(api, db_session)
    r = await api.patch(f"/api/sources/{sub['id']}", headers=h, json={"muted": True})
    assert r.status_code == 200 and r.json()["muted"] is True
    assert await _titles(api, h) == []  # hidden from aggregate views
    assert len(await _titles(api, h, f"&source={src.id}")) == 3  # but the feed itself shows

    # The public API (e.g. OneDay) sees the same filtering.
    k = await api.post("/api/keys", headers=h, json={"name": "t", "scopes": []})
    pub = await api.get("/api/v1/articles", headers={"X-API-Key": k.json()["key"]})
    assert pub.json()["items"] == []

    await api.patch(f"/api/sources/{sub['id']}", headers=h, json={"muted": False})
    assert len(await _titles(api, h)) == 3


async def test_keyword_validation(api: AsyncClient) -> None:
    h = _h(await _register(api))
    assert (
        await api.post("/api/filters/keywords", headers=h, json={"keyword": ""})
    ).status_code == 422
    a = await api.post("/api/filters/keywords", headers=h, json={"keyword": "war"})
    b = await api.post("/api/filters/keywords", headers=h, json={"keyword": "WAR"})
    assert a.json()["id"] == b.json()["id"]  # idempotent
    assert len((await api.get("/api/filters/keywords", headers=h)).json()) == 1
