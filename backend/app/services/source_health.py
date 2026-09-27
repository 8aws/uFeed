"""Feed health: which subscriptions are failing, stale or waiting."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_state import ArticleState
from app.models.source import Source
from app.models.subscription import Subscription

Status = Literal["ok", "retrying", "failing", "stale", "pending", "paused"]
FAILING_AFTER = 3  # consecutive failed fetches
STALE_AFTER = timedelta(days=30)  # no new article for this long


def status_for(src: Source, last_article_at: datetime | None) -> Status:
    if not src.is_active:
        return "paused"
    if src.error_count >= FAILING_AFTER:
        return "failing"
    if src.error_count > 0:
        return "retrying"
    if src.last_fetch_at is None:
        return "pending"
    if last_article_at is None or last_article_at < datetime.now(UTC) - STALE_AFTER:
        return "stale"
    return "ok"


def _last_article():
    return (
        select(
            Article.source_id,
            func.max(func.coalesce(Article.published_at, Article.fetched_at)).label("at"),
        )
        .group_by(Article.source_id)
        .subquery()
    )


@dataclass(slots=True)
class HealthRow:
    source: Source
    status: Status
    last_article_at: datetime | None
    subscription_id: uuid.UUID | None = None
    title: str | None = None
    subscribers: int = 0


async def for_user(db: AsyncSession, user_id: uuid.UUID) -> list[HealthRow]:
    last = _last_article()
    rows = (
        await db.execute(
            select(Subscription, Source, last.c.at)
            .join(Source, Source.id == Subscription.source_id)
            .outerjoin(last, last.c.source_id == Source.id)
            .where(Subscription.user_id == user_id)
        )
    ).all()
    out = [
        HealthRow(
            source=src,
            status=status_for(src, at),
            last_article_at=at,
            subscription_id=sub.id,
            title=sub.custom_title or src.title or src.feed_url,
        )
        for sub, src, at in rows
    ]
    return sorted(out, key=_problems_first)


async def for_admin(db: AsyncSession) -> list[HealthRow]:
    last = _last_article()
    subs = (
        select(Subscription.source_id, func.count().label("n"))
        .group_by(Subscription.source_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Source, last.c.at, func.coalesce(subs.c.n, 0))
            .outerjoin(last, last.c.source_id == Source.id)
            .outerjoin(subs, subs.c.source_id == Source.id)
        )
    ).all()
    out = [
        HealthRow(
            source=src,
            status=status_for(src, at),
            last_article_at=at,
            title=src.title or src.feed_url,
            subscribers=int(n),
        )
        for src, at, n in rows
    ]
    return sorted(out, key=_problems_first)


_ORDER = {"failing": 0, "retrying": 1, "paused": 2, "stale": 3, "pending": 4, "ok": 5}


def _problems_first(r: HealthRow) -> tuple:
    return (_ORDER[r.status], (r.title or "").lower())


async def set_paused(db: AsyncSession, source: Source, paused: bool) -> Source:
    source.is_active = not paused
    if not paused:  # retry soon, from a clean slate
        source.error_count = 0
        source.last_error = None
        source.next_fetch_at = None
    await db.commit()
    return source


async def delete_orphans(db: AsyncSession) -> int:
    """Delete feeds nobody follows, unless someone saved/favourited one of
    their articles. Returns how many were removed."""
    keeps = (
        select(Article.id)
        .join(ArticleState, ArticleState.article_id == Article.id)
        .where(
            Article.source_id == Source.id,
            or_(ArticleState.is_saved.is_(True), ArticleState.is_favorite.is_(True)),
        )
    )
    stmt = delete(Source).where(
        ~exists().where(Subscription.source_id == Source.id), ~exists(keeps)
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
