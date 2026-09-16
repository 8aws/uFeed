from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_state import ArticleState
from app.models.source import Source
from app.models.subscription import Subscription


@dataclass(slots=True)
class SubscriptionRow:
    subscription: Subscription
    source: Source
    unread_count: int


def _unread_subquery(user_id: uuid.UUID):
    return (
        select(func.count(Article.id))
        .select_from(Article)
        .outerjoin(
            ArticleState,
            and_(
                ArticleState.article_id == Article.id,
                ArticleState.user_id == user_id,
            ),
        )
        .where(
            Article.source_id == Subscription.source_id,
            or_(ArticleState.is_read.is_(None), ArticleState.is_read.is_(False)),
        )
        .correlate(Subscription)
        .scalar_subquery()
    )


async def list_subscriptions(db: AsyncSession, user_id: uuid.UUID) -> list[SubscriptionRow]:
    unread = _unread_subquery(user_id)
    stmt = (
        select(Subscription, Source, unread.label("unread"))
        .join(Source, Source.id == Subscription.source_id)
        .where(Subscription.user_id == user_id)
        .order_by(func.coalesce(Subscription.custom_title, Source.title, Source.feed_url))
    )
    rows = await db.execute(stmt)
    return [SubscriptionRow(sub, src, unread or 0) for sub, src, unread in rows.all()]


async def get_subscription_row(
    db: AsyncSession, user_id: uuid.UUID, subscription_id: uuid.UUID
) -> SubscriptionRow | None:
    unread = _unread_subquery(user_id)
    stmt = (
        select(Subscription, Source, unread.label("unread"))
        .join(Source, Source.id == Subscription.source_id)
        .where(Subscription.id == subscription_id, Subscription.user_id == user_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    sub, src, cnt = row
    return SubscriptionRow(sub, src, cnt or 0)


async def subscribe(
    db: AsyncSession,
    user_id: uuid.UUID,
    url: str,
    folder_id: uuid.UUID | None,
) -> tuple[Subscription, bool]:
    """Subscribe a user to a feed URL, creating/reusing the shared Source.

    Returns (subscription, created) where created is False if the user was
    already subscribed.
    """
    feed_url = url.strip()
    source = (
        await db.execute(select(Source).where(Source.feed_url == feed_url))
    ).scalar_one_or_none()
    if source is None:
        # next_fetch_at stays NULL so the ingestion worker picks it up promptly.
        source = Source(feed_url=feed_url)
        db.add(source)
        await db.flush()

    existing = (
        await db.execute(
            select(Subscription).where(
                Subscription.user_id == user_id, Subscription.source_id == source.id
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False

    sub = Subscription(user_id=user_id, source_id=source.id, folder_id=folder_id)
    db.add(sub)
    await db.commit()
    await db.refresh(sub)
    return sub, True


async def unsubscribe(db: AsyncSession, user_id: uuid.UUID, subscription_id: uuid.UUID) -> bool:
    sub = (
        await db.execute(
            select(Subscription).where(
                Subscription.id == subscription_id, Subscription.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if sub is None:
        return False
    await db.delete(sub)
    await db.commit()
    return True
