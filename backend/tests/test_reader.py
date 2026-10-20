from __future__ import annotations

import uuid
from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select
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


async def test_assign_subscription_to_folder(api: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _register(api)
    src = await _seed_source(db_session, [("A", "a")])
    sub = await _subscribe(api, headers, src.feed_url)
    folder = (await api.post("/api/folders", headers=headers, json={"name": "Tech"})).json()

    moved = await api.patch(
        f"/api/sources/{sub['id']}", headers=headers, json={"folder_id": folder["id"]}
    )
    assert moved.status_code == 200
    assert moved.json()["folder_id"] == folder["id"]

    # Filtering by that folder now returns the feed's article.
    listed = (await api.get(f"/api/articles?folder={folder['id']}", headers=headers)).json()
    assert len(listed["items"]) == 1

    # Move back to root (folder_id explicitly null).
    back = await api.patch(f"/api/sources/{sub['id']}", headers=headers, json={"folder_id": None})
    assert back.json()["folder_id"] is None


async def test_collapse_duplicates(api: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _register(api)
    src = Source(feed_url=f"https://ex.com/{uuid.uuid4().hex}.xml", title="Dup")
    db_session.add(src)
    await db_session.flush()
    seed = Article(
        source_id=src.id, guid="s", title="Seed", published_at=datetime(2025, 1, 2, tzinfo=UTC)
    )
    dupe = Article(
        source_id=src.id, guid="d", title="Dupe", published_at=datetime(2025, 1, 1, tzinfo=UTC)
    )
    db_session.add_all([seed, dupe])
    await db_session.flush()
    seed.dup_group_id = seed.id
    dupe.dup_group_id = seed.id  # same group -> a duplicate of the seed
    await db_session.commit()
    await _subscribe(api, headers, src.feed_url)

    collapsed = (await api.get("/api/articles", headers=headers)).json()["items"]
    assert [a["id"] for a in collapsed] == [str(seed.id)]
    assert collapsed[0]["dup_count"] == 2

    everything = (await api.get("/api/articles?collapse=false", headers=headers)).json()["items"]
    assert {a["id"] for a in everything} == {str(seed.id), str(dupe.id)}


async def _grouped(db: AsyncSession, seed_in: Source, copy_in: Source) -> tuple[Article, Article]:
    """A duplicate group made across two feeds: the seed in one, a copy in the other."""
    seed = Article(
        source_id=seed_in.id,
        guid=f"seed-{uuid.uuid4().hex}",
        title="Same story",
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    copy = Article(
        source_id=copy_in.id,
        guid=f"copy-{uuid.uuid4().hex}",
        title="Same story (copy)",
        published_at=datetime(2025, 1, 2, tzinfo=UTC),
    )
    db.add_all([seed, copy])
    await db.flush()
    seed.dup_group_id = seed.id
    copy.dup_group_id = seed.id
    await db.commit()
    return seed, copy


async def test_copy_of_a_story_seeded_by_a_feed_you_do_not_follow_still_shows(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    """Groups are instance-wide: another user's feed may hold the seed. The
    copy you can see must not vanish from your lists (it counted in the
    unread badge but never showed)."""
    other = await _seed_source(db_session, [])
    mine = await _seed_source(db_session, [])
    seed, copy = await _grouped(db_session, seed_in=other, copy_in=mine)
    headers = await _register(api)
    sub = await _subscribe(api, headers, mine.feed_url)
    assert sub["unread_count"] == 1

    mixed = (await api.get("/api/articles?unread=true", headers=headers)).json()["items"]
    assert [a["id"] for a in mixed] == [str(copy.id)]
    assert mixed[0]["dup_count"] == 1  # the seed isn't yours to count
    assert seed.id != copy.id


async def test_feed_list_matches_its_unread_badge(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    """Following both feeds, the mixed views show the story once, but opening a
    feed lists everything it published, so its badge and its list agree."""
    a = await _seed_source(db_session, [("A only", "x")])
    b = await _seed_source(db_session, [])
    seed, copy = await _grouped(db_session, seed_in=b, copy_in=a)
    headers = await _register(api)
    sub_a = await _subscribe(api, headers, a.feed_url)
    await _subscribe(api, headers, b.feed_url)

    mixed = (await api.get("/api/articles?unread=true", headers=headers)).json()["items"]
    ids = {x["id"] for x in mixed}
    assert str(seed.id) in ids and str(copy.id) not in ids  # one per story

    feed_a = (await api.get(f"/api/articles?unread=true&source={a.id}", headers=headers)).json()[
        "items"
    ]
    assert len(feed_a) == 2  # "A only" and the copy
    listed = (await api.get("/api/sources", headers=headers)).json()
    badge = next(s["unread_count"] for s in listed if s["id"] == sub_a["id"])
    assert badge == len(feed_a)


async def _follow_as_other_user(api: AsyncClient, feed_url: str) -> None:
    """A second person following a feed (so it counts as shared, not private)."""
    other = await _register(api)
    await _subscribe(api, other, feed_url)


async def test_unread_counts_only_follow_your_own_feeds(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    """The total and the folder numbers equal what their lists hold: one per
    story, only from feeds you follow. Copies in feeds you don't follow never
    count, even when they were the first of their group."""
    other = await _seed_source(db_session, [("Elsewhere", "e")])
    mine = await _seed_source(db_session, [("Mine only", "m")])
    other_art = (
        await db_session.execute(select(Article).where(Article.source_id == other.id))
    ).scalar_one()
    seed, copy = await _grouped(db_session, seed_in=other, copy_in=mine)
    headers = await _register(api)
    sub = await _subscribe(api, headers, mine.feed_url)
    folder = (await api.post("/api/folders", headers=headers, json={"name": "F"})).json()
    await api.patch(f"/api/sources/{sub['id']}", headers=headers, json={"folder_id": folder["id"]})

    counts = (await api.get("/api/articles/unread-counts", headers=headers)).json()
    listed = (await api.get("/api/articles?unread=true", headers=headers)).json()["items"]
    assert counts["total"] == len(listed) == 2  # "Mine only" + the copy of the shared story
    assert counts["folders"][folder["id"]] == 2
    in_folder = (
        await api.get(f"/api/articles?unread=true&folder={folder['id']}", headers=headers)
    ).json()["items"]
    assert len(in_folder) == counts["folders"][folder["id"]]
    assert str(other_art.id) not in {a["id"] for a in listed}
    assert str(seed.id) not in {a["id"] for a in listed}

    # Reading one lowers the numbers right away.
    first = listed[0]["id"]
    await api.post(f"/api/articles/{first}/read", headers=headers)
    after = (await api.get("/api/articles/unread-counts", headers=headers)).json()
    assert after["total"] == 1


async def test_copies_elsewhere_are_a_hint_and_can_be_listed(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    other = await _seed_source(db_session, [])
    mine = await _seed_source(db_session, [])
    seed, copy = await _grouped(db_session, seed_in=other, copy_in=mine)
    await _follow_as_other_user(api, other.feed_url)  # a shared feed, not a private one
    headers = await _register(api)
    await _subscribe(api, headers, mine.feed_url)

    items = (await api.get("/api/articles", headers=headers)).json()["items"]
    assert [a["id"] for a in items] == [str(copy.id)]
    assert items[0]["dup_count"] == 1  # none of the copies is in your feeds
    assert items[0]["other_copies"] == 1  # but the story is in a feed you don't follow

    twins = (await api.get(f"/api/articles/{copy.id}/twins", headers=headers)).json()
    assert len(twins) == 1
    t = twins[0]
    assert t["followed"] is False and t["article_id"] is None
    assert t["title"] == seed.title and "feed_url" not in t
    # Their article stays closed: only the title and the link are shared.
    assert (await api.get(f"/api/articles/{seed.id}", headers=headers)).status_code == 404


async def test_a_feed_only_one_person_follows_is_never_hinted_to_others(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    """A single follower may be using a private feed URL: its articles stay out
    of everyone else's "also published in" hints."""
    private = await _seed_source(db_session, [])
    mine = await _seed_source(db_session, [])
    seed, copy = await _grouped(db_session, seed_in=private, copy_in=mine)
    owner = await _register(api)
    await _subscribe(api, owner, private.feed_url)  # the only follower
    headers = await _register(api)
    await _subscribe(api, headers, mine.feed_url)

    items = (await api.get("/api/articles", headers=headers)).json()["items"]
    assert items[0]["other_copies"] == 0
    assert (await api.get(f"/api/articles/{copy.id}/twins", headers=headers)).json() == []


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
