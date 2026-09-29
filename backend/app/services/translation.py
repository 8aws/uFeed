"""Article translation for "read in my language" (AI service, opus-mt).

Translated once per article and language, stored, and shared by every reader
of that language; ~3-4 s for a 750-word article on the NAS CPU.
"""

from __future__ import annotations

import re

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.text import plain
from app.models.article import Article
from app.models.article_translation import ArticleTranslation

MODEL = "opus-mt"
MAX_PARAGRAPHS = 400

_DROP = re.compile(
    r"<(script|style|pre|code|figure|figcaption|table|audio|video)\b.*?</\1>"
    r"|<a\b[^>]*data-embed[^>]*>.*?</a>",
    re.I | re.S,
)
_BLOCK_END = re.compile(r"</(p|h[1-6]|li|blockquote|div|section|article|dd|dt)>|<br\s*/?>", re.I)
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def pairs() -> set[str]:
    return {p.strip() for p in settings.mt_pairs.split(",") if p.strip()}


def source_lang(article: Article) -> str:
    return (article.lang or "").split("-")[0].split("_")[0].lower()


def paragraphs(article: Article) -> list[str]:
    """Plain-text paragraphs of the body (no code, captions, tables, media)."""
    body = _DROP.sub(" ", article.content_html or article.summary or "")
    parts = _BLOCK_END.sub("\n\n", body).split("\n\n")
    out = []
    for p in parts:
        text = _WS.sub(" ", plain(_TAG.sub(" ", p)) or "").strip()
        if text:
            out.append(text)
    return out[:MAX_PARAGRAPHS]


async def translate(db: AsyncSession, article: Article, lang: str) -> ArticleTranslation | None:
    """Translate and store; None if the AI service is unavailable."""
    src = source_lang(article)
    paras = paragraphs(article)
    title = (plain(article.title) or "").strip()
    if not settings.ai_enabled or not (paras or title):
        return None
    try:
        async with httpx.AsyncClient(timeout=settings.mt_timeout_s) as client:
            resp = await client.post(
                f"{settings.ai_url}/translate",
                json={"texts": [title, *paras], "src": src, "dst": lang},
            )
        if resp.status_code != 200:
            return None
        texts = resp.json()["texts"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None
    rec = ArticleTranslation(
        article_id=article.id,
        lang=lang,
        title=texts[0] or None,
        paragraphs=[t for t in texts[1:] if t],
        model=MODEL,
    )
    await db.merge(rec)
    await db.commit()
    return rec


def speech_text(tr: ArticleTranslation) -> str:
    """What the server voice reads for a translation."""
    body = " ".join(p if p[-1:] in ".!?…:;" else f"{p}." for p in tr.paragraphs)
    return f"{tr.title}. {body}" if tr.title else body
