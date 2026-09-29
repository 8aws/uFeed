"""Server voice for "listen": article text -> MP3 from the AI service (Piper),
cached on disk and shared by every reader of that article and language.

Playback goes through short-lived signed URLs (an <audio> element can't send
the Authorization header, and a JWT must never sit in a URL).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
import time
import uuid
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.ratelimit import get_redis
from app.core.text import plain
from app.models.article import Article

URL_TTL_S = 6 * 3600
MAX_WORDS = 6000  # ~40 min of speech

_DROP = re.compile(
    r"<(script|style|pre|code|figure|figcaption|table|audio|video)\b.*?</\1>|<a\b[^>]*data-embed[^>]*>.*?</a>",
    re.I | re.S,
)
_BLOCK_END = re.compile(r"</(p|h[1-6]|li|blockquote|div|section|article)>|<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_DOTS = re.compile(r"([.!?…:;])\s*\.(\s|$)")
_NAME = re.compile(r"^[0-9a-f-]{36}-[a-z]{2}[fm]-[a-z0-9]{1,8}\.mp3$")


def supported_langs() -> set[str]:
    return {x.strip() for x in settings.tts_langs.split(",") if x.strip()}


def lang_of(article: Article, requested: str | None) -> str | None:
    """Voice language: the article's own (the text is read as written)."""
    lang = (article.lang or requested or "").split("-")[0].split("_")[0].lower()
    return lang if lang in supported_langs() else None


def speech_text(article: Article) -> str:
    """Plain text to read: title, then the body without code, captions,
    tables or media; block ends become pauses."""
    body = article.content_html or article.summary or ""
    body = _DROP.sub(" ", body)
    body = _BLOCK_END.sub(". ", body)
    text = plain(_TAG.sub(" ", body)) or ""
    text = _WS.sub(" ", text).strip()
    text = _DOTS.sub(r"\1\2", text).strip(" .")
    words = text.split(" ")
    if len(words) > MAX_WORDS:
        text = " ".join(words[:MAX_WORDS]) + "…"
    title = (plain(article.title) or "").strip()
    return f"{title}. {text}" if title else text


def cache_name(article_id: uuid.UUID, lang: str, gender: str) -> str:
    return f"{article_id}-{lang}{gender}-{settings.tts_voice_tag}.mp3"


def cache_path(name: str) -> Path:
    return Path(settings.tts_cache_dir) / name


def _sig(name: str, exp: int) -> str:
    msg = f"tts|{name}|{exp}".encode()
    return hmac.new(settings.jwt_secret.encode(), msg, hashlib.sha256).hexdigest()[:32]


def signed_url(name: str) -> str:
    exp = int(time.time()) + URL_TTL_S
    return f"/api/audio/{name}?exp={exp}&sig={_sig(name, exp)}"


def verify(name: str, exp: int, sig: str) -> bool:
    return (
        bool(_NAME.match(name)) and exp >= time.time() and hmac.compare_digest(sig, _sig(name, exp))
    )


def cached(name: str) -> bool:
    p = cache_path(name)
    if p.exists() and p.stat().st_size > 0:
        os.utime(p)  # most recently used: last to be evicted
        return True
    return False


async def generate(name: str, text: str, lang: str, gender: str) -> bool:
    """Ask the AI service for the MP3 and store it. False if unavailable."""
    if not settings.ai_enabled or not text:
        return False
    try:
        async with httpx.AsyncClient(timeout=settings.tts_timeout_s) as client:
            resp = await client.post(
                f"{settings.ai_url}/tts", json={"text": text, "lang": lang, "gender": gender}
            )
    except httpx.HTTPError:
        return False
    if resp.status_code != 200 or not resp.content:
        return False
    path = cache_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(resp.content)
    os.replace(tmp, path)
    prune()
    return True


# --- Live generation: play while the article is still being read out ----------
#
# The request that asks for audio starts the generation in the background
# (AI /tts/stream) and gets its URL at once. The MP3 is written to <name>.part
# as it arrives and renamed to <name>.mp3 when complete. Every playback request
# -- the first, a retry, or the duplicate probe iOS sends -- streams whatever
# is written and follows the file until it's done, in any backend worker.
# A Redis lock makes sure one article/voice is generated once.

LIVE_IDLE_S = 60  # give up following a .part that stopped growing
_tasks: set[asyncio.Task] = set()


def part_path(name: str) -> Path:
    return cache_path(name).with_suffix(".part")


def _err_path(name: str) -> Path:
    return cache_path(name).with_suffix(".err")


def in_progress(name: str) -> bool:
    """Being generated: a .part that is still growing (a stale one, left by a
    restarted worker, doesn't count and gets regenerated)."""
    try:
        return time.time() - part_path(name).stat().st_mtime < LIVE_IDLE_S
    except FileNotFoundError:
        return False


async def start_live(name: str, text: str, lang: str, gender: str) -> bool:
    """Kick off background generation unless it's done or already running.
    False if the server voice can't be used at all."""
    if not settings.ai_enabled or not text:
        return False
    if cached(name):
        return True
    try:
        got = await get_redis().set(f"ttsgen:{name}", "1", nx=True, ex=int(settings.tts_timeout_s))
    except Exception:  # noqa: BLE001 - no Redis: fall back to this worker only
        got = not in_progress(name)
    if not got:
        return True  # someone is generating it right now
    part = part_path(name)
    part.parent.mkdir(parents=True, exist_ok=True)
    part.write_bytes(b"")
    _err_path(name).unlink(missing_ok=True)
    task = asyncio.create_task(_generate_live(name, text, lang, gender))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return True


async def _generate_live(name: str, text: str, lang: str, gender: str) -> None:
    part = part_path(name)
    ok = False
    try:
        async with httpx.AsyncClient(timeout=settings.tts_timeout_s) as client:
            async with client.stream(
                "POST",
                f"{settings.ai_url}/tts/stream",
                json={"text": text, "lang": lang, "gender": gender},
            ) as resp:
                if resp.status_code == 200:
                    with part.open("ab") as f:
                        async for chunk in resp.aiter_bytes():
                            f.write(chunk)
                            f.flush()
                    ok = part.stat().st_size > 0
    except (httpx.HTTPError, OSError):
        ok = False
    if ok:
        os.replace(part, cache_path(name))
        prune()
    else:
        _err_path(name).write_text("failed")
        part.unlink(missing_ok=True)
    try:
        await get_redis().delete(f"ttsgen:{name}")
    except Exception:  # noqa: BLE001
        pass


async def follow_live(name: str):
    """Yield the MP3 as it's being written, until complete (or stalled)."""
    part, final, err = part_path(name), cache_path(name), _err_path(name)
    offset, idle = 0, 0.0
    while True:
        src = part if part.exists() else final if final.exists() else None
        if src is None:
            if err.exists():
                return
            await asyncio.sleep(0.2)
            idle += 0.2
            if idle > 10:
                return
            continue
        try:
            with src.open("rb") as f:
                f.seek(offset)
                data = f.read()
        except FileNotFoundError:
            continue  # renamed between exists() and open(): read the final file
        if data:
            offset += len(data)
            idle = 0.0
            yield data
        elif src == final:
            return  # complete
        else:
            await asyncio.sleep(0.2)
            idle += 0.2
            if idle > LIVE_IDLE_S:
                return


def prune() -> None:
    """Keep the cache under tts_cache_max_mb, dropping least recently used."""
    root = Path(settings.tts_cache_dir)
    files = sorted(root.glob("*.mp3"), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    limit = settings.tts_cache_max_mb * 1024 * 1024
    for p in files:
        if total <= limit:
            break
        total -= p.stat().st_size
        p.unlink(missing_ok=True)
