from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.article import Article
from app.models.article_translation import ArticleTranslation
from app.services import translation, tts
from tests.test_admin import _h, _register, _set_role
from tests.test_reader import _seed_source, _subscribe


@pytest.fixture
def fake_mt(monkeypatch, tmp_path):
    calls: list[str] = []

    async def fake_translate(db, article, lang):
        calls.append(lang)
        rec = ArticleTranslation(
            article_id=article.id,
            lang=lang,
            title=f"[{lang}] {article.title}",
            paragraphs=[f"[{lang}] {p}" for p in translation.paragraphs(article)],
            model="fake",
        )
        await db.merge(rec)
        await db.commit()
        return rec

    async def fake_voice(name, text, lang, gender):
        calls.append(f"tts:{lang}:{text}")
        (tmp_path / name).write_bytes(b"ID3" + b"\0" * 64)
        return True

    monkeypatch.setattr(translation, "translate", fake_translate)
    monkeypatch.setattr(tts, "generate", fake_voice)
    monkeypatch.setattr(settings, "tts_cache_dir", str(tmp_path))
    return calls


async def _english_article(api: AsyncClient, db: AsyncSession, role: str = "general"):
    src = await _seed_source(
        db, [("Hello", "<p>First paragraph.</p><pre>code</pre><h2>Next</h2><p>Second one.</p>")]
    )
    r = await _register(api)
    await _set_role(db, r.json()["user"]["id"], role)
    h = _h(r)
    await _subscribe(api, h, src.feed_url)
    aid = (await api.get("/api/articles", headers=h)).json()["items"][0]["id"]
    await db.execute(update(Article).where(Article.id == uuid.UUID(aid)).values(lang="en"))
    await db.commit()
    return h, aid


async def test_translate_on_demand_and_cache(
    api: AsyncClient, db_session: AsyncSession, fake_mt
) -> None:
    h, aid = await _english_article(api, db_session)
    # Nothing until asked; then generated once and shared.
    r = (await api.get(f"/api/articles/{aid}/translation?lang=es", headers=h)).json()
    assert r["paragraphs"] is None and r["source_lang"] == "en"
    r = (await api.get(f"/api/articles/{aid}/translation?lang=es&generate=true", headers=h)).json()
    assert r["title"] == "[es] Hello" and r["cached"] is False
    assert r["paragraphs"] == ["[es] First paragraph.", "[es] Next", "[es] Second one."]
    r = (await api.get(f"/api/articles/{aid}/translation?lang=es&generate=true", headers=h)).json()
    assert r["cached"] is True and fake_mt == ["es"]
    # Same language: nothing to translate.
    r = await api.get(f"/api/articles/{aid}/translation?lang=en&generate=true", headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "mt_pair"


async def test_server_voice_reads_the_translation(
    api: AsyncClient, db_session: AsyncSession, fake_mt
) -> None:
    h, aid = await _english_article(api, db_session)
    r = await api.post(f"/api/articles/{aid}/audio?lang=es&translated=true", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["lang"] == "es"
    spoken = [c for c in fake_mt if c.startswith("tts:")][0]
    assert spoken.startswith("tts:es:[es] Hello. [es] First paragraph.")
