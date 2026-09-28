from __future__ import annotations

import base64
import binascii
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy import and_, case, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.article import Article
from app.models.article_state import ArticleState
from app.models.hidden_article import HiddenArticle
from app.models.read_event import ReadEvent
from app.models.source import Source
from app.models.subscription import Subscription
from app.services import filters as filters_service
from app.services.ai import embed_texts

# Sort key: prefer published_at, fall back to fetched_at (always present).
_SORT_TS = func.coalesce(Article.published_at, Article.fetched_at)


@dataclass(slots=True)
class ArticleRow:
    article: Article
    is_read: bool
    is_saved: bool
    is_favorite: bool = False
    dup_count: int = 1


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


@dataclass(slots=True)
class RankedRow:
    row: ArticleRow
    readers: int
    quality: float
    saves: int
    favorites: int
    opens: int
    score: float


@dataclass(slots=True)
class Insights:
    trending_now: list[RankedRow]
    top: list[RankedRow]
    most_saved: list[RankedRow]
    deep_reads: list[RankedRow]
    hidden_gems: list[RankedRow]

    def all_article_ids(self) -> set[uuid.UUID]:
        ids: set[uuid.UUID] = set()
        for lst in (
            self.trending_now,
            self.top,
            self.most_saved,
            self.deep_reads,
            self.hidden_gems,
        ):
            ids.update(r.row.article.id for r in lst)
        return ids


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
    semantic: bool = False,
    cursor: str | None = None,
    limit: int = 50,
    collapse: bool = True,
) -> ArticlePage:
    # Count of articles sharing this one's dedup group (1 when ungrouped).
    dup_alias = aliased(Article)
    dup_count_expr = case(
        (
            Article.dup_group_id.isnot(None),
            select(func.count())
            .select_from(dup_alias)
            .where(dup_alias.dup_group_id == Article.dup_group_id)
            .scalar_subquery(),
        ),
        else_=1,
    )
    stmt = _base_query(user_id).add_columns(dup_count_expr)

    # Collapse near-duplicates: show only the group seed (id == group) or
    # articles not yet grouped.
    if collapse:
        stmt = stmt.where(or_(Article.dup_group_id.is_(None), Article.dup_group_id == Article.id))

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

    # Mutes: hide muted feeds from aggregate views (a feed you open explicitly
    # still shows) and articles matching muted keywords. Saved/favourites are
    # never filtered — you kept them on purpose.
    if not saved and not favorite:
        mutes = await filters_service.load(db, user_id)
        if source is None:
            stmt = stmt.where(Subscription.muted.is_(False))
        kw = filters_service.keyword_clause(mutes.keywords)
        if kw is not None:
            stmt = stmt.where(kw)

    # Semantic search: rank by embedding distance to the query vector. Falls
    # back to full-text below if the AI service is unavailable.
    if q and semantic:
        qvec = await embed_texts([q])
        if qvec:
            stmt = (
                stmt.where(Article.embedding.isnot(None))
                .order_by(Article.embedding.cosine_distance(qvec[0]))
                .limit(limit)
            )
            result = (await db.execute(stmt)).all()
            rows = [
                ArticleRow(a, bool(r), bool(s), bool(f), int(dc or 1)) for a, r, s, f, dc in result
            ]
            return ArticlePage(rows=rows, next_cursor=None)

    if q:
        # Match article title/content (full-text) or the source name.
        stmt = stmt.join(Source, Source.id == Article.source_id).where(
            or_(
                _fts_vector().op("@@")(func.plainto_tsquery("simple", q)),
                Source.title.ilike(f"%{q}%"),
            )
        )

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
    rows = [
        ArticleRow(a, bool(r), bool(s), bool(f), int(dc or 1)) for a, r, s, f, dc in result[:limit]
    ]

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
    before: datetime | None = None,
) -> int:
    """Mark every matching subscribed article as read (set-based upsert).
    With `before`, only articles fetched up to then (an offline press synced
    later must not swallow what arrived afterwards)."""
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
    if before is not None:
        sel = sel.where(Article.fetched_at <= min(_aware(before), datetime.now(UTC)))

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


# Events recorded offline arrive late; older than this they no longer matter
# to any ranking window (max 30 days) and are accepted but not stored.
EVENT_MAX_AGE = timedelta(days=30)


def _aware(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def _event_time(at: datetime | None) -> tuple[bool, datetime | None]:
    """(keep, created_at): client time clamped to now; None = server time."""
    if at is None:
        return True, None
    now = datetime.now(UTC)
    at = min(_aware(at), now)
    return now - at <= EVENT_MAX_AGE, at


async def record_read_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    article_id: uuid.UUID,
    dwell_ms: int,
    completion: float,
    *,
    at: datetime | None = None,
) -> bool:
    """Record one anonymised reading event for cross-user trending."""
    if not await _user_owns_article(db, user_id, article_id):
        return False
    keep, created = _event_time(at)
    if not keep:
        return True
    ev = ReadEvent(
        article_id=article_id,
        user_id=user_id,
        dwell_ms=max(0, dwell_ms),
        completion=max(0.0, min(1.0, completion)),
    )
    if created is not None:
        ev.created_at = created
    db.add(ev)
    await db.commit()
    return True


_ALLOWED_ENGAGE = {"open", "share", "skip"}


async def record_engagement(
    db: AsyncSession,
    user_id: uuid.UUID,
    article_id: uuid.UUID,
    kind: str,
    *,
    at: datetime | None = None,
) -> bool:
    """Record a non-reading engagement event (open original / share / skip)."""
    if kind not in _ALLOWED_ENGAGE:
        return False
    if not await _user_owns_article(db, user_id, article_id):
        return False
    keep, created = _event_time(at)
    if not keep:
        return True
    ev = ReadEvent(article_id=article_id, user_id=user_id, kind=kind)
    if created is not None:
        ev.created_at = created
    db.add(ev)
    await db.commit()
    return True


async def _articles_with_state(
    db: AsyncSession, user_id: uuid.UUID, ids: set[uuid.UUID]
) -> dict[uuid.UUID, ArticleRow]:
    """Fetch articles (global, not just subscribed) + this user's state."""
    if not ids:
        return {}
    stmt = (
        select(Article, ArticleState.is_read, ArticleState.is_saved, ArticleState.is_favorite)
        .outerjoin(
            ArticleState,
            and_(ArticleState.article_id == Article.id, ArticleState.user_id == user_id),
        )
        .where(Article.id.in_(ids))
    )
    mutes = await filters_service.load(db, user_id)
    out: dict[uuid.UUID, ArticleRow] = {}
    for a, r, s, f in (await db.execute(stmt)).all():
        if not (s or f) and mutes.hides(a):  # trending/similar/for-you respect mutes
            continue
        out[a.id] = ArticleRow(a, bool(r), bool(s), bool(f))
    return out


async def rows_for_ids(
    db: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID]
) -> list[ArticleRow]:
    """Hydrate a list of article ids with the user's state, preserving order."""
    m = await _articles_with_state(db, user_id, set(ids))
    return [m[i] for i in ids if i in m]


async def insights(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    window_hours: int = 720,  # 30 days, so the trending bar isn't empty early on
    half_life_hours: float = 10.0,
    limit: int = 12,
) -> Insights:
    """Compute several content rankings from anonymised engagement."""
    since = datetime.now(UTC) - timedelta(hours=window_hours)

    # Reading metrics per article (length-normalised dwell + recency-decayed velocity).
    expected_ms = func.greatest(func.coalesce(Article.word_count, 0), 50) / 220.0 * 60000.0
    norm_dwell = func.least(1.0, ReadEvent.dwell_ms / expected_ms)
    age_hours = func.extract("epoch", func.now() - ReadEvent.created_at) / 3600.0
    weighted = func.sum(func.power(0.5, age_hours / half_life_hours))
    read_stmt = (
        select(
            ReadEvent.article_id.label("aid"),
            func.count(func.distinct(ReadEvent.user_id)).label("readers"),
            func.avg(ReadEvent.completion).label("avg_completion"),
            func.avg(norm_dwell).label("avg_norm_dwell"),
            weighted.label("weighted"),
        )
        .join(Article, Article.id == ReadEvent.article_id)
        .where(
            ReadEvent.kind == "read",
            ReadEvent.created_at >= since,
            ReadEvent.article_id.not_in(select(HiddenArticle.article_id)),
        )
        .group_by(ReadEvent.article_id)
    )
    reads = {r.aid: r for r in (await db.execute(read_stmt)).all()}
    if not reads:
        return Insights([], [], [], [], [])

    # open/share/skip counts.
    eng_stmt = (
        select(ReadEvent.article_id, ReadEvent.kind, func.count().label("n"))
        .where(ReadEvent.kind.in_(["open", "share", "skip"]), ReadEvent.created_at >= since)
        .group_by(ReadEvent.article_id, ReadEvent.kind)
    )
    opens: dict[uuid.UUID, int] = {}
    shares: dict[uuid.UUID, int] = {}
    skips: dict[uuid.UUID, int] = {}
    for aid, kind, n in (await db.execute(eng_stmt)).all():
        {"open": opens, "share": shares, "skip": skips}[kind][aid] = n

    # Saves / favorites (all-time) for the candidate articles.
    ids = set(reads)
    state_stmt = (
        select(
            ArticleState.article_id,
            func.count().filter(ArticleState.is_saved.is_(True)).label("saves"),
            func.count().filter(ArticleState.is_favorite.is_(True)).label("favorites"),
        )
        .where(ArticleState.article_id.in_(ids))
        .group_by(ArticleState.article_id)
    )
    saves: dict[uuid.UUID, int] = {}
    favs: dict[uuid.UUID, int] = {}
    for aid, s, f in (await db.execute(state_stmt)).all():
        saves[aid] = s
        favs[aid] = f

    art_rows = await _articles_with_state(db, user_id, ids)

    metrics = []
    for aid, r in reads.items():
        if aid not in art_rows:
            continue
        quality = 0.5 * float(r.avg_completion or 0) + 0.5 * float(r.avg_norm_dwell or 0)
        m = {
            "aid": aid,
            "readers": int(r.readers or 0),
            "quality": quality,
            "weighted": float(r.weighted or 0),
            "saves": saves.get(aid, 0),
            "favorites": favs.get(aid, 0),
            "opens": opens.get(aid, 0),
            "shares": shares.get(aid, 0),
            "skips": skips.get(aid, 0),
        }
        metrics.append(m)

    def ranked(scored: list[tuple[dict, float]]) -> list[RankedRow]:
        scored = [x for x in scored if x[1] > 0]
        scored.sort(key=lambda x: x[1], reverse=True)
        rows = []
        for m, score in scored[:limit]:
            rows.append(
                RankedRow(
                    row=art_rows[m["aid"]],
                    readers=m["readers"],
                    quality=round(m["quality"], 3),
                    saves=m["saves"],
                    favorites=m["favorites"],
                    opens=m["opens"],
                    score=round(score, 3),
                )
            )
        return rows

    top = ranked([(m, m["readers"] * (0.5 + m["quality"]) - 0.5 * m["skips"]) for m in metrics])
    trending_now = ranked([(m, m["weighted"] * (0.5 + m["quality"])) for m in metrics])
    most_saved = ranked(
        [(m, m["saves"] * 2 + m["favorites"] * 3 + m["opens"] + m["shares"] * 2) for m in metrics]
    )
    deep_reads = ranked([(m, m["quality"] if m["readers"] >= 2 else 0.0) for m in metrics])
    hidden_gems = ranked(
        [
            (
                m,
                (
                    m["quality"] * (1 + m["saves"] + 2 * m["favorites"])
                    if (
                        m["readers"] <= 3
                        and m["quality"] >= 0.5
                        and (m["saves"] + m["favorites"]) > 0
                    )
                    else 0.0
                ),
            )
            for m in metrics
        ]
    )
    return Insights(trending_now, top, most_saved, deep_reads, hidden_gems)


async def trending(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    window_hours: int = 720,  # 30 days, so the trending bar isn't empty early on
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
        .where(
            ReadEvent.created_at >= since,
            ReadEvent.article_id.not_in(select(HiddenArticle.article_id)),
        )
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
