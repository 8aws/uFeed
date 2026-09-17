from __future__ import annotations

import re
import uuid

import httpx
from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.article import Article
from app.models.article_state import ArticleState
from app.models.subscription import Subscription

_TAG_RE = re.compile(r"<[^>]+>")


def _embed_text(a: Article) -> str:
    body = _TAG_RE.sub(" ", a.content_html or a.summary or "")
    return f"{a.title or ''}\n{body}"[:2000]


async def embed_texts(texts: list[str]) -> list[list[float]] | None:
    """Call the AI service to embed texts. Returns None if AI is unavailable."""
    if not settings.ai_enabled or not texts:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{settings.ai_url}/embed", json={"texts": texts})
            resp.raise_for_status()
            return resp.json()["vectors"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None


async def summarize_texts(texts: list[str]) -> list[str] | None:
    """Call the AI service to summarise texts. None if AI is unavailable."""
    if not settings.ai_enabled or not texts:
        return None
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.ai_url}/summarize_batch",
                json={"texts": texts, "max_sentences": settings.ai_summary_sentences},
            )
            resp.raise_for_status()
            return resp.json()["summaries"]
    except (httpx.HTTPError, KeyError, ValueError):
        return None


async def summarize_pending(db: AsyncSession, limit: int | None = None) -> int:
    """Generate an AI summary for articles that lack one."""
    limit = limit or settings.summarize_max_per_tick
    rows = (
        (
            await db.execute(
                select(Article)
                .where(
                    Article.ai_summary.is_(None),
                    or_(Article.content_html.isnot(None), Article.summary.isnot(None)),
                )
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0
    texts = [(a.content_html or a.summary or "")[:6000] for a in rows]
    summaries = await summarize_texts(texts)
    if summaries is None:
        return 0
    written = 0
    for article, summary in zip(rows, summaries, strict=False):
        summary = (summary or "").strip()
        if summary:
            await db.execute(
                update(Article).where(Article.id == article.id).values(ai_summary=summary)
            )
            written += 1
    await db.commit()
    return written


async def embed_pending(db: AsyncSession, limit: int | None = None) -> int:
    """Embed articles that don't yet have a vector. Returns how many embedded."""
    limit = limit or settings.embed_max_per_tick
    rows = (
        (await db.execute(select(Article).where(Article.embedding.is_(None)).limit(limit)))
        .scalars()
        .all()
    )
    if not rows:
        return 0
    vectors = await embed_texts([_embed_text(a) for a in rows])
    if vectors is None:
        return 0
    for article, vec in zip(rows, vectors, strict=False):
        await db.execute(update(Article).where(Article.id == article.id).values(embedding=vec))
    await db.commit()
    return len(rows)


async def similar_articles(
    db: AsyncSession, user_id: uuid.UUID, article_id: uuid.UUID, limit: int = 8
) -> list[Article]:
    """Articles most similar (cosine) to a given one, within the user's subs."""
    target = (
        await db.execute(select(Article.embedding).where(Article.id == article_id))
    ).scalar_one_or_none()
    if target is None:
        return []
    stmt = (
        select(Article)
        .join(Subscription, Subscription.source_id == Article.source_id)
        .where(
            Subscription.user_id == user_id,
            Article.id != article_id,
            Article.embedding.isnot(None),
        )
        .order_by(Article.embedding.cosine_distance(target))
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def for_you(db: AsyncSession, user_id: uuid.UUID, limit: int = 20) -> list[Article]:
    """Recommend unread articles near the user's taste profile.

    Profile = mean embedding of articles the user engaged with (read/saved/
    favorited). Requires embeddings to be present.
    """
    liked = (
        (
            await db.execute(
                select(Article.embedding)
                .join(ArticleState, ArticleState.article_id == Article.id)
                .where(
                    ArticleState.user_id == user_id,
                    Article.embedding.isnot(None),
                    or_(
                        ArticleState.is_saved.is_(True),
                        ArticleState.is_favorite.is_(True),
                        ArticleState.is_read.is_(True),
                    ),
                )
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    if not liked:
        return []

    dim = len(liked[0])
    profile = [0.0] * dim
    for vec in liked:
        for i, v in enumerate(vec):
            profile[i] += float(v)
    profile = [v / len(liked) for v in profile]

    stmt = (
        select(Article)
        .join(Subscription, Subscription.source_id == Article.source_id)
        .outerjoin(
            ArticleState,
            and_(ArticleState.article_id == Article.id, ArticleState.user_id == user_id),
        )
        .where(
            Subscription.user_id == user_id,
            Article.embedding.isnot(None),
            or_(ArticleState.is_read.is_(None), ArticleState.is_read.is_(False)),
        )
        .order_by(Article.embedding.cosine_distance(profile))
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
