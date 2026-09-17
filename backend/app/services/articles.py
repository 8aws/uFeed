from __future__ import annotations

import base64
import binascii
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy import and_, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.article import Article
from app.models.article_state import ArticleState
from app.models.read_event import ReadEvent
from app.models.subscription import Subscription

# Sort key: prefer published_at, fall back to fetched_at (always present).
_SORT_TS = func.coalesce(Article.published_at, Article.fetched_at)


@dataclass(slots=True)
class ArticleRow:
    article: Article
    is_read: bool
    is_saved: bool
    is_favorite: bool = False


@dataclass(slots=True)
class ArticlePage:
    rows: list[ArticleRow]
    next_cursor: str | None


@dataclass(slots=True)
class TrendingRow:
    row: ArticleRow
    readers: int
    avg_completion: float
    avg_dwell_ms: int
    score: float


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
        select(Article, ArticleState.is_read, ArticleState.is_saved, ArticleState.is_favorite)
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
    favorite: bool | None = None,
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
    if favorite is True:
        stmt = stmt.where(ArticleState.is_favorite.is_(True))
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
    rows = [ArticleRow(a, bool(r), bool(s), bool(f)) for a, r, s, f in result[:limit]]

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
    article, is_read, is_saved, is_favorite = row
    return ArticleRow(article, bool(is_read), bool(is_saved), bool(is_favorite))


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
    is_favorite: bool | None = None,
) -> bool:
    """Upsert the per-user read/saved/favorite state for one article."""
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
    if is_favorite is not None:
        values["is_favorite"] = is_favorite
        set_["is_favorite"] = is_favorite

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


async def record_read_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    article_id: uuid.UUID,
    dwell_ms: int,
    completion: float,
) -> bool:
    """Record one anonymised reading event for cross-user trending."""
    if not await _user_owns_article(db, user_id, article_id):
        return False
    db.add(
        ReadEvent(
            article_id=article_id,
            user_id=user_id,
            dwell_ms=max(0, dwell_ms),
            completion=max(0.0, min(1.0, completion)),
        )
    )
    await db.commit()
    return True


async def trending(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    window_hours: int = 48,
    limit: int = 8,
) -> list[TrendingRow]:
    """Most-read articles across all users in a time window (anonymised)."""
    since = datetime.now(UTC) - timedelta(hours=window_hours)
    agg = (
        select(
            ReadEvent.article_id.label("aid"),
            func.count(func.distinct(ReadEvent.user_id)).label("readers"),
            func.avg(ReadEvent.completion).label("avg_completion"),
            func.avg(ReadEvent.dwell_ms).label("avg_dwell"),
        )
        .where(ReadEvent.created_at >= since)
        .group_by(ReadEvent.article_id)
        .subquery()
    )
    # Importance: more distinct readers, weighted up by how fully they read it.
    score = (agg.c.readers * (1.0 + func.coalesce(agg.c.avg_completion, 0.0))).label("score")
    stmt = (
        select(
            Article,
            ArticleState.is_read,
            ArticleState.is_saved,
            ArticleState.is_favorite,
            agg.c.readers,
            agg.c.avg_completion,
            agg.c.avg_dwell,
            score,
        )
        .join(agg, agg.c.aid == Article.id)
        .outerjoin(
            ArticleState,
            and_(ArticleState.article_id == Article.id, ArticleState.user_id == user_id),
        )
        .order_by(score.desc())
        .limit(limit)
    )
    out: list[TrendingRow] = []
    for a, r, s, f, readers, avg_c, avg_d, sc in (await db.execute(stmt)).all():
        out.append(
            TrendingRow(
                row=ArticleRow(a, bool(r), bool(s), bool(f)),
                readers=int(readers or 0),
                avg_completion=float(avg_c or 0.0),
                avg_dwell_ms=int(avg_d or 0),
                score=float(sc or 0.0),
            )
        )
    return out
