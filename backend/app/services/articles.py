from __future__ import annotations

import base64
import binascii
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import and_, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_state import ArticleState
from app.models.subscription import Subscription

# Sort key: prefer published_at, fall back to fetched_at (always present).
_SORT_TS = func.coalesce(Article.published_at, Article.fetched_at)


@dataclass(slots=True)
class ArticleRow:
    article: Article
    is_read: bool
    is_saved: bool


@dataclass(slots=True)
class ArticlePage:
    rows: list[ArticleRow]
    next_cursor: str | None


def _fts_vector():
    return func.to_tsvector(
        "simple",
        func.coalesce(Article.title, "") + " " + func.coalesce(Article.content_html, ""),
    )


def encode_cursor(ts: datetime, article_id: uuid.UUID) -> str:
    raw = f"{ts.isoformat()}|{article_id}".encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_s, id_s = raw.split("|", 1)
        return datetime.fromisoformat(ts_s), uuid.UUID(id_s)
    except (ValueError, binascii.Error):
        return None


def _base_query(user_id: uuid.UUID):
    """Articles from the user's subscriptions, with their per-user state."""
    return (
        select(Article, ArticleState.is_read, ArticleState.is_saved)
        .join(Subscription, Subscription.source_id == Article.source_id)
        .outerjoin(
            ArticleState,
            and_(ArticleState.article_id == Article.id, ArticleState.user_id == user_id),
        )
        .where(Subscription.user_id == user_id)
    )


async def list_articles(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    folder: uuid.UUID | None = None,
    source: uuid.UUID | None = None,
    unread: bool | None = None,
    saved: bool | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> ArticlePage:
    stmt = _base_query(user_id)

    if source is not None:
        stmt = stmt.where(Article.source_id == source)
    if folder is not None:
        stmt = stmt.where(Subscription.folder_id == folder)
    if unread is True:
        stmt = stmt.where(or_(ArticleState.is_read.is_(None), ArticleState.is_read.is_(False)))
    elif unread is False:
        stmt = stmt.where(ArticleState.is_read.is_(True))
    if saved is True:
        stmt = stmt.where(ArticleState.is_saved.is_(True))
    elif saved is False:
        stmt = stmt.where(or_(ArticleState.is_saved.is_(None), ArticleState.is_saved.is_(False)))
    if q:
        stmt = stmt.where(_fts_vector().op("@@")(func.plainto_tsquery("simple", q)))

    if cursor:
        decoded = decode_cursor(cursor)
        if decoded is not None:
            cts, cid = decoded
            stmt = stmt.where(
                tuple_(_SORT_TS, Article.id)
                < tuple_(
                    sa.literal(cts, type_=sa.DateTime(timezone=True)),
                    sa.literal(cid, type_=sa.Uuid()),
                )
            )

    stmt = stmt.order_by(_SORT_TS.desc(), Article.id.desc()).limit(limit + 1)

    result = (await db.execute(stmt)).all()
    rows = [ArticleRow(a, bool(r), bool(s)) for a, r, s in result[:limit]]

    next_cursor = None
    if len(result) > limit:
        last = rows[-1].article
        sort_ts = last.published_at or last.fetched_at
        next_cursor = encode_cursor(sort_ts, last.id)
    return ArticlePage(rows=rows, next_cursor=next_cursor)


async def get_article(
    db: AsyncSession, user_id: uuid.UUID, article_id: uuid.UUID
) -> ArticleRow | None:
    stmt = _base_query(user_id).where(Article.id == article_id)
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    article, is_read, is_saved = row
    return ArticleRow(article, bool(is_read), bool(is_saved))


async def _user_owns_article(db: AsyncSession, user_id: uuid.UUID, article_id: uuid.UUID) -> bool:
    stmt = (
        select(Article.id)
        .join(Subscription, Subscription.source_id == Article.source_id)
        .where(Subscription.user_id == user_id, Article.id == article_id)
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None


async def set_state(
    db: AsyncSession,
    user_id: uuid.UUID,
    article_id: uuid.UUID,
    *,
    is_read: bool | None = None,
    is_saved: bool | None = None,
) -> bool:
    """Upsert the per-user read/saved state for one article."""
    if not await _user_owns_article(db, user_id, article_id):
        return False

    values: dict = {"user_id": user_id, "article_id": article_id}
    set_: dict = {}
    if is_read is not None:
        values["is_read"] = is_read
        set_["is_read"] = is_read
        values["read_at"] = datetime.now(UTC) if is_read else None
        set_["read_at"] = values["read_at"]
    if is_saved is not None:
        values["is_saved"] = is_saved
        set_["is_saved"] = is_saved

    stmt = (
        pg_insert(ArticleState)
        .values(**values)
        .on_conflict_do_update(index_elements=["user_id", "article_id"], set_=set_)
    )
    await db.execute(stmt)
    await db.commit()
    return True


async def mark_all_read(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    folder: uuid.UUID | None = None,
    source: uuid.UUID | None = None,
) -> int:
    """Mark every matching subscribed article as read (set-based upsert)."""
    sel = (
        select(
            sa.literal(user_id, type_=sa.Uuid()).label("user_id"),
            Article.id.label("article_id"),
            sa.true().label("is_read"),
            func.now().label("read_at"),
        )
        .select_from(Article)
        .join(Subscription, Subscription.source_id == Article.source_id)
        .where(Subscription.user_id == user_id)
    )
    if source is not None:
        sel = sel.where(Article.source_id == source)
    if folder is not None:
        sel = sel.where(Subscription.folder_id == folder)

    stmt = (
        pg_insert(ArticleState)
        .from_select(["user_id", "article_id", "is_read", "read_at"], sel)
        .on_conflict_do_update(
            index_elements=["user_id", "article_id"],
            set_={"is_read": sa.true(), "read_at": func.now()},
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0
