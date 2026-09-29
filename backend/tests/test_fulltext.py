from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.services import fulltext, tts
from tests.test_admin import _h, _register
from tests.test_reader import _seed_source, _subscribe

PARA = "This is a long paragraph of the real article with plenty of words to read. " * 6
PAGE = f"""<html><head><title>x</title></head><body><nav>Home News Sport</nav>
<article><h1>The headline</h1><p>{PARA}</p><h2>Details</h2><p>{PARA}</p>
<ul><li>First point of the story</li><li>Second point of the story</li></ul>
<p>{PARA}</p></article><footer>Copyright</footer></body></html>"""


async def _excerpt_article(api: AsyncClient, db: AsyncSession):
    src = await _seed_source(db, [("Short one", "<p>Just a teaser.</p>")])
    h = _h(await _register(api))
    await _subscribe(api, h, src.feed_url)
    aid = (await api.get("/api/articles", headers=h)).json()["items"][0]["id"]
    await db.execute(
        update(Article).where(Article.id == uuid.UUID(aid)).values(url="https://news.example/a")
    )
    await db.commit()
    return h, aid


async def test_full_text_fetched_once(api, db_session, monkeypatch) -> None:
    calls: list[str] = []

    async def fake_download(url: str) -> str:
        calls.append(url)
        return PAGE

    monkeypatch.setattr(fulltext, "_download", fake_download)
    h, aid = await _excerpt_article(api, db_session)
    r = (await api.post(f"/api/articles/{aid}/full", headers=h)).json()
    assert r["status"] == "ok" and r["words"] > 200
    assert "<h2>" in r["html"] and "<li>" in r["html"] and "Copyright" not in r["html"]
    # Stored and shared: no second download; the list says it's there.
    r2 = (await api.post(f"/api/articles/{aid}/full", headers=h)).json()
    assert r2["html"] == r["html"] and calls == ["https://news.example/a"]
    item = (await api.get("/api/articles", headers=h)).json()["items"][0]
    assert item["full_status"] == "ok"
    # The voice reads the full text, not the teaser.
    art = await db_session.get(Article, uuid.UUID(aid))
    await db_session.refresh(art)
    assert "real article" in tts.speech_text(art) and "teaser" not in tts.speech_text(art)


async def test_full_text_not_better_is_failed(api, db_session, monkeypatch) -> None:
    async def tiny(url: str) -> str:
        return "<html><body><p>Just a teaser.</p></body></html>"

    monkeypatch.setattr(fulltext, "_download", tiny)
    h, aid = await _excerpt_article(api, db_session)
    r = (await api.post(f"/api/articles/{aid}/full", headers=h)).json()
    assert r["status"] == "failed" and r["html"] is None
