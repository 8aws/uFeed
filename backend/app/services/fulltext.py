"""Full article text for feeds that only publish an excerpt.

Downloads the article page (through the SSRF-guarded client, like feeds) and
extracts the main content with trafilatura, keeping paragraphs, headings,
lists, images and links. Stored on the article and shared by every reader;
a failed attempt is remembered for a day so pages that block us aren't
hammered. When the full text arrives, translations and recordings made from
the excerpt are dropped (they're regenerated on demand from the full text).
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.netguard import BlockedDestination, public_client
from app.models.article import Article
from app.models.article_ai import ArticleAI
from app.models.article_translation import ArticleTranslation
from app.services import metrics
from app.services.ingest import http_url

MAX_BYTES = 3 * 1024 * 1024
RETRY_AFTER = timedelta(days=1)
_TAG = re.compile(r"<[^>]+>")
_WRAP = re.compile(r"</?(html|body)[^>]*>", re.I)


def words(html: str | None) -> int:
    return len(_TAG.sub(" ", html or "").split())


async def _download(url: str) -> str | None:
    headers = {"User-Agent": settings.user_agent, "Accept": "text/html,application/xhtml+xml"}
    async with public_client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        async with client.stream("GET", url) as resp:
            if resp.status_code != 200:
                return None
            if "html" not in resp.headers.get("content-type", "html"):
                return None
            body = bytearray()
            async for chunk in resp.aiter_bytes():
                body += chunk
                if len(body) > MAX_BYTES:
                    return None
            return body.decode(resp.encoding or "utf-8", errors="replace")


def _extract(page: str, url: str) -> str | None:
    import trafilatura

    out = trafilatura.extract(
        page,
        url=url,
        output_format="html",
        include_images=True,
        include_links=True,
        include_tables=True,
        favor_precision=True,
    )
    return _WRAP.sub("", out).strip() if out else None


async def fetch(db: AsyncSession, article: Article) -> str | None:
    """The article's full HTML (fetched once), or None if not available."""
    if article.full_status == "ok" and article.full_html:
        return article.full_html
    now = datetime.now(UTC)
    if (
        article.full_status == "failed"
        and article.full_fetched_at
        and (now - article.full_fetched_at < RETRY_AFTER)
    ):
        return None
    url = http_url(article.url)
    if not url:
        return None
    t0 = time.monotonic()
    html = None
    try:
        page = await _download(url)
        if page:
            html = await asyncio.to_thread(_extract, page, url)
    except (httpx.HTTPError, BlockedDestination, ValueError):
        html = None
    excerpt = words(article.content_html or article.summary)
    # Only worth it if it's clearly more than the feed already gave us.
    ok = bool(html) and words(html) >= max(60, int(excerpt * 1.3))
    article.full_status = "ok" if ok else "failed"
    article.full_fetched_at = now
    article.full_html = html if ok else None
    if ok:
        # Made from the excerpt: redo them from the full text when asked.
        await db.execute(
            delete(ArticleTranslation).where(ArticleTranslation.article_id == article.id)
        )
        await db.execute(delete(ArticleAI).where(ArticleAI.article_id == article.id))
    await db.commit()
    if ok:
        _drop_recordings(str(article.id))
        await metrics.count("full", int((time.monotonic() - t0) * 1000))
    return article.full_html


def _drop_recordings(article_id: str) -> None:
    from pathlib import Path

    for p in Path(settings.tts_cache_dir).glob(f"{article_id}-*.mp3"):
        p.unlink(missing_ok=True)


def body_html(article: Article) -> str:
    """What to read/translate: the full text when we have it."""
    if article.full_status == "ok" and article.full_html:
        return article.full_html
    return article.content_html or article.summary or ""
