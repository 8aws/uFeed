"""Per-user content filters: muted keywords and muted sources."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import and_, func, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.muted_keyword import MutedKeyword
from app.models.subscription import Subscription

MAX_KEYWORDS = 100


@dataclass(slots=True)
class Mutes:
    keywords: list[str] = field(default_factory=list)
    sources: set[uuid.UUID] = field(default_factory=set)

    def hides(self, article: Article) -> bool:
        if article.source_id in self.sources:
            return True
        text = f"{article.title or ''} {article.summary or ''}".lower()
        return any(k in text for k in self.keywords)


def normalize(keyword: str) -> str:
    return " ".join((keyword or "").split()).lower()[:100]


async def load(db: AsyncSession, user_id: uuid.UUID) -> Mutes:
    kws = (
        await db.execute(select(MutedKeyword.keyword).where(MutedKeyword.user_id == user_id))
    ).scalars()
    srcs = (
        await db.execute(
            select(Subscription.source_id).where(
                Subscription.user_id == user_id, Subscription.muted.is_(True)
            )
        )
    ).scalars()
    return Mutes(keywords=[k for k in kws if k], sources=set(srcs))


def _like(keyword: str) -> str:
    esc = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{esc}%"


def keyword_clause(keywords: list[str]):
    """SQL condition that is true when an article matches none of the keywords."""
    if not keywords:
        return None
    parts = []
    for kw in keywords:
        pat = _like(kw)
        parts.append(
            not_(
                or_(
                    func.coalesce(Article.title, "").ilike(pat, escape="\\"),
                    func.coalesce(Article.summary, "").ilike(pat, escape="\\"),
                )
            )
        )
    return and_(*parts)


async def list_keywords(db: AsyncSession, user_id: uuid.UUID) -> list[MutedKeyword]:
    rows = await db.execute(
        select(MutedKeyword).where(MutedKeyword.user_id == user_id).order_by(MutedKeyword.keyword)
    )
    return list(rows.scalars().all())


async def add_keyword(db: AsyncSession, user_id: uuid.UUID, keyword: str) -> MutedKeyword | None:
    """Add (idempotent). Returns None if the keyword is empty or the cap is hit."""
    kw = normalize(keyword)
    if not kw:
        return None
    existing = (
        await db.execute(
            select(MutedKeyword).where(MutedKeyword.user_id == user_id, MutedKeyword.keyword == kw)
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    count = await db.scalar(
        select(func.count()).select_from(MutedKeyword).where(MutedKeyword.user_id == user_id)
    )
    if (count or 0) >= MAX_KEYWORDS:
        return None
    row = MutedKeyword(user_id=user_id, keyword=kw)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def remove_keyword(db: AsyncSession, user_id: uuid.UUID, keyword_id: uuid.UUID) -> bool:
    row = await db.get(MutedKeyword, keyword_id)
    if row is None or row.user_id != user_id:
        return False
    await db.delete(row)
    await db.commit()
    return True
