from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.ratelimit import get_redis
from app.models.article import Article
from app.models.read_event import ReadEvent
from app.models.user import User
from app.services import digest, mailer
from tests.test_admin import _h, _register, _set_role
from tests.test_reader import _seed_source, _subscribe

PW = "supersecret1"


@pytest.fixture
def outbox(monkeypatch) -> list[dict]:
    """Capture outgoing mail instead of sending it."""
    get_redis.cache_clear()  # the app's Redis client, for this test's loop
    sent: list[dict] = []

    async def fake_send(to, subject, text, html=None, headers=None, images=None):
        sent.append(
            {
                "to": to,
                "subject": subject,
                "text": text,
                "html": html,
                "headers": headers,
                "images": images or {},
            }
        )
        return True

    monkeypatch.setattr(mailer, "send", fake_send)
    monkeypatch.setattr(mailer, "enabled", lambda: True)
    return sent


def _link_token(text: str) -> str:
    return re.search(r"token=([\w.-]+)", text).group(1)


async def test_password_reset_by_email(api: AsyncClient, outbox: list[dict]) -> None:
    r = await _register(api)
    email = r.json()["user"]["email"]
    old_session = _h(r)

    unknown = await api.post("/api/auth/forgot", json={"email": "nobody@example.com"})
    assert unknown.status_code == 200 and outbox == []  # same answer, no mail

    assert (await api.post("/api/auth/forgot", json={"email": email})).status_code == 200
    assert len(outbox) == 1 and outbox[0]["to"] == email
    assert f"{settings.public_url}/reset?token=" in outbox[0]["text"]
    token = _link_token(outbox[0]["text"])

    short = await api.post("/api/auth/reset", json={"token": token, "new_password": "short"})
    assert short.status_code == 422
    done = await api.post("/api/auth/reset", json={"token": token, "new_password": "brandnew123"})
    assert done.status_code == 200, done.text
    assert "access_token" in done.json()

    login = await api.post("/api/auth/login", json={"email": email, "password": "brandnew123"})
    assert login.status_code == 200
    old = await api.post("/api/auth/login", json={"email": email, "password": PW})
    assert old.status_code == 401
    assert (await api.get("/api/me", headers=old_session)).status_code == 401  # signed out

    # The link works once.
    again = await api.post("/api/auth/reset", json={"token": token, "new_password": "another123"})
    assert again.status_code == 400 and again.json()["error"]["code"] == "invalid_reset"


async def test_reset_rejects_other_tokens_and_limits_mail(
    api: AsyncClient, outbox: list[dict]
) -> None:
    r = await _register(api)
    email = r.json()["user"]["email"]
    access = r.json()["tokens"]["access_token"]
    bad = await api.post("/api/auth/reset", json={"token": access, "new_password": "brandnew123"})
    assert bad.status_code == 400  # a session token is not a reset link

    for _ in range(5):
        await api.post("/api/auth/forgot", json={"email": email})
    assert len(outbox) == 3  # at most 3 emails an hour per address


async def test_protected_demo_account_gets_no_reset(
    api: AsyncClient, outbox: list[dict], monkeypatch
) -> None:
    r = await _register(api)
    email = r.json()["user"]["email"]
    monkeypatch.setattr(settings, "protected_accounts", email)
    await api.post("/api/auth/forgot", json={"email": email})
    assert outbox == []


async def _reader_with_news(
    api: AsyncClient, db: AsyncSession, n: int = 5
) -> tuple[dict, list[str]]:
    r = await _register(api)
    h = _h(r)
    src = await _seed_source(
        db, [(f"Noticia {i}", f"<p>Texto {i} " * 20 + "</p>") for i in range(n)]
    )
    now = datetime.now(UTC)
    rows = (await db.execute(select(Article).where(Article.source_id == src.id))).scalars().all()
    for i, a in enumerate(rows):
        a.published_at = now - timedelta(hours=i + 1)
    await db.commit()
    await _subscribe(api, h, src.feed_url)
    items = (await api.get("/api/articles", headers=h)).json()["items"]
    return h, [a["id"] for a in items]


async def test_digest_picks_read_and_fresh_with_a_cap_per_feed(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    h, ids = await _reader_with_news(api, db_session, n=5)
    # Two other people read the oldest one: it goes first.
    for _ in range(2):
        other = await _register(api)
        db_session.add(
            ReadEvent(
                user_id=uuid.UUID(other.json()["user"]["id"]),
                article_id=uuid.UUID(ids[-1]),
                dwell_ms=60_000,
                completion=1.0,
            )
        )
    await db_session.commit()
    d = (await api.get("/api/digest", headers=h)).json()
    assert d["total_new"] == 5
    assert len(d["items"]) == 3  # at most three from the same feed
    assert d["items"][0]["id"] == ids[-1] and d["items"][0]["readers"] == 2
    assert d["items"][0]["summary"].startswith("Texto")


async def test_digest_email_hour_and_unsubscribe(
    api: AsyncClient, db_session: AsyncSession, outbox: list[dict]
) -> None:
    h, _ = await _reader_with_news(api, db_session, n=2)
    me = (await api.patch("/api/me", headers=h, json={"digest_hour": 0})).json()
    assert me["digest_hour"] == 0
    user = await db_session.get(User, uuid.UUID(me["id"]))
    # Chosen at an hour already gone today: the first one goes out tomorrow.
    assert user.digest_sent_on == digest._local_now().date()

    user.digest_sent_on = None
    await db_session.commit()
    assert await digest.send_one(db_session, user, date.today()) is True
    mail = outbox[-1]
    assert "uFeed" in mail["subject"] and "Noticia" in mail["html"]
    assert mail["headers"]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    off = await api.get(f"/api/digest/off?token={_link_token(mail['text'].split()[-1])}")
    assert off.status_code == 200
    await db_session.refresh(user)
    assert user.digest_hour is None

    bad = await api.get("/api/digest/off?token=nope")
    assert bad.status_code == 400


async def test_digest_by_api_key(api: AsyncClient, db_session: AsyncSession) -> None:
    h, _ = await _reader_with_news(api, db_session, n=1)
    me = (await api.get("/api/me", headers=h)).json()
    await _set_role(db_session, me["id"], "general")  # a plan with API keys
    key = (await api.post("/api/keys", headers=h, json={"name": "oneday"})).json()
    r = await api.get("/api/v1/digest", headers={"X-API-Key": key["key"]})
    assert r.status_code == 200 and r.json()["total_new"] == 1


async def test_digest_summaries_are_queued_ahead(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    from app.services import ai_queue

    get_redis.cache_clear()
    h, ids = await _reader_with_news(api, db_session, n=2)
    me = (await api.get("/api/me", headers=h)).json()
    user = await db_session.get(User, uuid.UUID(me["id"]))
    assert await digest.prepare(db_session, user) == 2  # both lack a summary
    status = await ai_queue.status(uuid.UUID(ids[0]), user.locale[:2])
    assert status["status"] == "queued"
    await get_redis().delete(ai_queue.PENDING)


async def test_digest_email_has_logo_and_feed_icons(
    api: AsyncClient, db_session: AsyncSession, outbox: list[dict], monkeypatch
) -> None:
    from app.models.source import Source
    from app.services import favicons

    h, ids = await _reader_with_news(api, db_session, n=1)
    art = await db_session.get(Article, uuid.UUID(ids[0]))
    src = await db_session.get(Source, art.source_id)
    src.favicon_url = "https://example.com/favicon.ico"
    await db_session.commit()

    async def fake_png(url):
        return b"\x89PNG-fake" if url == "https://example.com/favicon.ico" else None

    monkeypatch.setattr(favicons, "png", fake_png)
    me = (await api.get("/api/me", headers=h)).json()
    user = await db_session.get(User, uuid.UUID(me["id"]))
    assert await digest.send_one(db_session, user, date.today()) is True
    mail = outbox[-1]
    assert "logo@ufeed" in mail["images"] and "cid:logo@ufeed" in mail["html"]
    icon_cids = [c for c in mail["images"] if c.startswith("feed")]
    assert len(icon_cids) == 1 and f"cid:{icon_cids[0]}" in mail["html"]


def test_feed_icons_become_small_pngs() -> None:
    import io

    from PIL import Image

    from app.services import favicons

    ico = io.BytesIO()
    Image.new("RGBA", (64, 64), (37, 99, 235, 255)).save(ico, "ICO", sizes=[(16, 16), (64, 64)])
    png = favicons._to_png(ico.getvalue())
    with Image.open(io.BytesIO(png)) as img:
        assert img.format == "PNG" and img.size == (32, 32)
    assert favicons._to_png(b"not an image") is None


async def test_digest_days(api: AsyncClient, db_session: AsyncSession) -> None:
    h, _ = await _reader_with_news(api, db_session, n=1)
    me = (await api.patch("/api/me", headers=h, json={"digest_hour": 8, "digest_days": 31})).json()
    assert me["digest_days"] == 31  # Monday to Friday
    user = await db_session.get(User, uuid.UUID(me["id"]))
    monday, saturday = date(2026, 10, 5), date(2026, 10, 10)
    assert digest.on_day(user, monday) and not digest.on_day(user, saturday)
    bad = await api.patch("/api/me", headers=h, json={"digest_days": 0})
    assert bad.status_code == 422  # at least one day
