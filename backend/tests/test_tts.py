from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.article import Article
from app.services import tts
from tests.test_admin import _h, _register, _set_role
from tests.test_reader import _seed_source, _subscribe

FAKE_MP3 = b"ID3" + b"\x00" * 2048


@pytest.fixture
def fake_voice(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "tts_cache_dir", str(tmp_path))
    calls: list[tuple[str, str, str]] = []

    async def fake_generate(name: str, text: str, lang: str, gender: str) -> bool:
        calls.append((text, lang, gender))
        (tmp_path / name).write_bytes(FAKE_MP3)
        return True

    monkeypatch.setattr(tts, "generate", fake_generate)
    return calls


async def _reader(api: AsyncClient, db: AsyncSession, role: str, lang: str | None = "es"):
    src = await _seed_source(
        db, [("Título", "<p>Hola mundo</p><pre>code()</pre><p><a data-embed='youtube:x'>▶</a></p>")]
    )
    r = await _register(api)
    await _set_role(db, r.json()["user"]["id"], role)
    h = _h(r)
    await _subscribe(api, h, src.feed_url)
    aid = (await api.get("/api/articles", headers=h)).json()["items"][0]["id"]
    await db.execute(update(Article).where(Article.id == uuid.UUID(aid)).values(lang=lang))
    await db.commit()
    return h, aid


async def test_server_voice_by_plan(api: AsyncClient, db_session: AsyncSession, fake_voice) -> None:
    h, aid = await _reader(api, db_session, "free")
    r = await api.post(f"/api/articles/{aid}/audio", headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "plan_limit_tts"

    h, aid = await _reader(api, db_session, "general")
    r = await api.post(f"/api/articles/{aid}/audio", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["lang"] == "es" and body["cached"] is False
    # Read as written: title first, no code or embed placeholders.
    text, lang, gender = fake_voice[0]
    assert text.startswith("Título.") and "Hola mundo" in text
    assert "code()" not in text and "▶" not in text and (lang, gender) == ("es", "f")

    # Second request is served from the cache (no new generation).
    again = (await api.post(f"/api/articles/{aid}/audio", headers=h)).json()
    assert again["cached"] is True and len(fake_voice) == 1

    # The other voice is a separate recording.
    male = (await api.post(f"/api/articles/{aid}/audio?voice=m", headers=h)).json()
    assert male["cached"] is False and fake_voice[-1][2] == "m" and male["url"] != body["url"]

    # The signed URL plays without a token; tampering or expiry is refused.
    play = await api.get(body["url"])
    assert play.status_code == 200 and play.headers["content-type"] == "audio/mpeg"
    assert play.content == FAKE_MP3
    ranged = await api.get(body["url"], headers={"Range": "bytes=0-9"})
    assert ranged.status_code == 206 and len(ranged.content) == 10
    assert (await api.get(body["url"][:-4] + "0000")).status_code == 403
    name = body["url"].split("/")[-1].split("?")[0]
    expired = f"/api/audio/{name}?exp=1&sig={tts._sig(name, 1)}"
    assert (await api.get(expired)).status_code == 403


async def test_server_voice_language(
    api: AsyncClient, db_session: AsyncSession, fake_voice
) -> None:
    h, aid = await _reader(api, db_session, "vip", lang="fr")
    r = await api.post(f"/api/articles/{aid}/audio", headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "tts_lang"
