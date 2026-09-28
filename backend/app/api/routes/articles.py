from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.errors import AppError
from app.core.config import settings
from app.core.ratelimit import check_rate
from app.models.article_ai import ArticleAI
from app.schemas.article import (
    AISummaryOut,
    ArticleOut,
    EngageRequest,
    MarkAllReadRequest,
    ReadEventRequest,
)
from app.schemas.common import OkResponse, Page
from app.schemas.user import Locale
from app.services import ai as ai_service
from app.services import articles as article_service
from app.services import site as site_service
from app.services.articles import ArticleRow

router = APIRouter(prefix="/articles", tags=["articles"])


def _to_out(row: ArticleRow) -> ArticleOut:
    out = ArticleOut.model_validate(row.article)
    out.is_read = row.is_read
    out.is_saved = row.is_saved
    out.is_favorite = row.is_favorite
    out.dup_count = row.dup_count
    return out


@router.get("", response_model=Page[ArticleOut])
async def list_articles(
    user: CurrentUser,
    db: DbSession,
    folder: uuid.UUID | None = None,
    source: uuid.UUID | None = None,
    unread: bool | None = None,
    saved: bool | None = None,
    favorite: bool | None = None,
    q: str | None = None,
    semantic: bool = False,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    collapse: bool = True,
) -> Page[ArticleOut]:
    if semantic and not (await site_service.limits_for(db, user.role))["ai_features"]:
        semantic = False  # plan without AI search: plain text search instead
    page = await article_service.list_articles(
        db,
        user.id,
        folder=folder,
        source=source,
        unread=unread,
        saved=saved,
        favorite=favorite,
        q=q,
        semantic=semantic,
        cursor=cursor,
        limit=limit,
        collapse=collapse,
    )
    return Page(items=[_to_out(r) for r in page.rows], next_cursor=page.next_cursor)


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(article_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ArticleOut:
    row = await article_service.get_article(db, user.id, article_id)
    if row is None:
        raise AppError(404, "not_found", "Article not found.")
    return _to_out(row)


@router.get("/{article_id}/similar", response_model=list[ArticleOut])
async def similar(
    article_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=8, ge=1, le=30),
) -> list[ArticleOut]:
    if not (await site_service.limits_for(db, user.role))["ai_features"]:
        return []
    arts = await ai_service.similar_articles(db, user.id, article_id, limit=limit)
    rows = await article_service.rows_for_ids(db, user.id, [a.id for a in arts])
    return [_to_out(r) for r in rows]


@router.get("/{article_id}/ai-summary", response_model=AISummaryOut)
async def ai_summary(
    article_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    lang: Locale | None = None,
    generate: bool = False,
) -> AISummaryOut:
    """The article's AI summary in `lang` (default: yours).

    Generated on demand (generate=true) by the on-device LLM and stored, so every
    later reader in that language gets it instantly. Without generate=true only
    an existing summary is returned.
    """
    row = await article_service.get_article(db, user.id, article_id)
    if row is None:
        raise AppError(404, "not_found", "Article not found.")
    lang = lang or user.locale
    cached = await db.get(ArticleAI, (article_id, lang))
    if cached is not None:
        return AISummaryOut(
            lang=lang, summary=cached.summary, title=cached.title, model=cached.model, cached=True
        )
    if not generate:
        return AISummaryOut(lang=lang)
    if not (await site_service.limits_for(db, user.role))["ai_features"]:
        raise AppError(403, "plan_limit_ai", "Your plan doesn't include AI features.")
    if not await check_rate(f"llm:{user.id}", settings.ai_llm_per_hour, window_s=3600):
        raise AppError(429, "rate_limited", "Too many AI summaries this hour; try later.")
    art = row.article
    translate = bool(art.lang) and not art.lang.lower().startswith(lang)
    out = await ai_service.llm_summary(
        art.title or "", art.content_html or art.summary or "", lang, translate
    )
    if out is None:
        raise AppError(503, "ai_unavailable", "The AI model is not available right now.")
    rec = ArticleAI(
        article_id=article_id,
        lang=lang,
        summary=out["summary"],
        title=out.get("title"),
        model=out.get("model") or "llm",
    )
    await db.merge(rec)
    await db.commit()
    return AISummaryOut(
        lang=lang, summary=rec.summary, title=rec.title, model=rec.model, cached=False
    )


async def _set_state(user, db, article_id, **kwargs) -> OkResponse:
    if not await article_service.set_state(db, user.id, article_id, **kwargs):
        raise AppError(404, "not_found", "Article not found.")
    return OkResponse()


@router.post("/{article_id}/read", response_model=OkResponse)
async def mark_read(article_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    return await _set_state(user, db, article_id, is_read=True)


@router.delete("/{article_id}/read", response_model=OkResponse)
async def mark_unread(article_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    return await _set_state(user, db, article_id, is_read=False)


@router.post("/{article_id}/save", response_model=OkResponse)
async def mark_saved(article_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    return await _set_state(user, db, article_id, is_saved=True)


@router.delete("/{article_id}/save", response_model=OkResponse)
async def mark_unsaved(article_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    return await _set_state(user, db, article_id, is_saved=False)


@router.post("/{article_id}/favorite", response_model=OkResponse)
async def mark_favorite(article_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    return await _set_state(user, db, article_id, is_favorite=True)


@router.delete("/{article_id}/favorite", response_model=OkResponse)
async def mark_unfavorite(article_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    return await _set_state(user, db, article_id, is_favorite=False)


@router.post("/{article_id}/read-event", response_model=OkResponse)
async def read_event(
    article_id: uuid.UUID, body: ReadEventRequest, user: CurrentUser, db: DbSession
) -> OkResponse:
    ok = await article_service.record_read_event(
        db, user.id, article_id, body.dwell_ms, body.completion, at=body.at
    )
    if not ok:
        raise AppError(404, "not_found", "Article not found.")
    return OkResponse()


@router.post("/{article_id}/engage", response_model=OkResponse)
async def engage(
    article_id: uuid.UUID, body: EngageRequest, user: CurrentUser, db: DbSession
) -> OkResponse:
    ok = await article_service.record_engagement(db, user.id, article_id, body.kind, at=body.at)
    if not ok:
        raise AppError(404, "not_found", "Article not found or invalid event.")
    return OkResponse()


@router.post("/mark-all-read", response_model=OkResponse)
async def mark_all_read(body: MarkAllReadRequest, user: CurrentUser, db: DbSession) -> OkResponse:
    await article_service.mark_all_read(
        db, user.id, folder=body.folder_id, source=body.source_id, before=body.before
    )
    return OkResponse()
