from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.source import Source


async def _register(api: AsyncClient) -> dict:
    r = await api.post(
        "/api/auth/register",
        json={"email": f"r-{uuid.uuid4().hex[:12]}@example.com", "password": "supersecret1"},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['tokens']['access_token']}"}


async def _seed_source(db: AsyncSession, articles: list[tuple[str, str]]) -> Source:
    src = Source(feed_url=f"https://ex.com/{uuid.uuid4().hex}.xml", title="Seeded Feed")
    db.add(src)
    await db.flush()
    for i, (title, body) in enumerate(articles):
        db.add(
            Article(
                source_id=src.id,
                guid=f"{src.id}-{i}",
                title=title,
                content_html=body,
                published_at=datetime(2025, 1, i + 1, tzinfo=UTC),
            )
        )
    await db.commit()
    return src


async def _subscribe(api: AsyncClient, headers: dict, feed_url: str, folder_id: str | None = None):
    payload: dict = {"url": feed_url}
    if folder_id:
        payload["folder_id"] = folder_id
    r = await api.post("/api/sources", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def test_subscribe_lists_with_unread_count(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _register(api)
    src = await _seed_source(db_session, [("A", "alpha"), ("B", "beta")])

    sub = await _subscribe(api, headers, src.feed_url)
    assert sub["source"]["feed_url"] == src.feed_url
    assert sub["unread_count"] == 2

    listed = await api.get("/api/sources", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["unread_count"] == 2


async def test_article_filters_and_search(api: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _register(api)
    src = await _seed_source(
        db_session, [("Python news", "about python"), ("Rust news", "about rust"), ("Go", "golang")]
    )
    await _subscribe(api, headers, src.feed_url)

    everything = (await api.get("/api/articles", headers=headers)).json()
    assert len(everything["items"]) == 3
    # Newest first (published_at desc): "Go" was seeded last.
    assert everything["items"][0]["title"] == "Go"

    # Mark the first as read -> unread filter drops it.
    first_id = everything["items"][0]["id"]
    assert (await api.post(f"/api/articles/{first_id}/read", headers=headers)).status_code == 200
    unread = (await api.get("/api/articles?unread=true", headers=headers)).json()
    assert len(unread["items"]) == 2
    assert first_id not in [a["id"] for a in unread["items"]]

    # Save one -> saved filter returns exactly it.
    assert (await api.post(f"/api/articles/{first_id}/save", headers=headers)).status_code == 200
    saved = (await api.get("/api/articles?saved=true", headers=headers)).json()
    assert [a["id"] for a in saved["items"]] == [first_id]

    # Full-text search.
    found = (await api.get("/api/articles?q=rust", headers=headers)).json()
    assert [a["title"] for a in found["items"]] == ["Rust news"]


async def test_cursor_pagination(api: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _register(api)
    src = await _seed_source(db_session, [(f"post {i}", f"body {i}") for i in range(3)])
    await _subscribe(api, headers, src.feed_url)

    page1 = (await api.get("/api/articles?limit=2", headers=headers)).json()
    assert len(page1["items"]) == 2
    assert page1["next_cursor"]

    page2 = (
        await api.get(f"/api/articles?limit=2&cursor={page1['next_cursor']}", headers=headers)
    ).json()
    assert len(page2["items"]) == 1
    assert page2["next_cursor"] is None

    ids = {a["id"] for a in page1["items"]} | {a["id"] for a in page2["items"]}
    assert len(ids) == 3  # no overlap, full coverage


async def test_mark_all_read(api: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _register(api)
    src = await _seed_source(db_session, [("A", "a"), ("B", "b"), ("C", "c")])
    await _subscribe(api, headers, src.feed_url)

    assert (
        await api.post("/api/articles/mark-all-read", headers=headers, json={})
    ).status_code == 200
    unread = (await api.get("/api/articles?unread=true", headers=headers)).json()
    assert unread["items"] == []


async def test_read_state_isolated_between_users(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    src = await _seed_source(db_session, [("Shared", "shared body")])
    a = await _register(api)
    b = await _register(api)
    await _subscribe(api, a, src.feed_url)
    await _subscribe(api, b, src.feed_url)

    a_articles = (await api.get("/api/articles", headers=a)).json()["items"]
    article_id = a_articles[0]["id"]
    await api.post(f"/api/articles/{article_id}/read", headers=a)

    # A sees it read, B still sees it unread.
    a_unread = (await api.get("/api/articles?unread=true", headers=a)).json()["items"]
    b_unread = (await api.get("/api/articles?unread=true", headers=b)).json()["items"]
    assert article_id not in [x["id"] for x in a_unread]
    assert article_id in [x["id"] for x in b_unread]


async def test_cannot_access_unsubscribed_article(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    src = await _seed_source(db_session, [("Secret", "hidden")])
    headers = await _register(api)  # not subscribed
    # Find the article id straight from the DB.
    from sqlalchemy import select

    article_id = (
        await db_session.execute(select(Article.id).where(Article.source_id == src.id))
    ).scalar_one()
    resp = await api.get(f"/api/articles/{article_id}", headers=headers)
    assert resp.status_code == 404
