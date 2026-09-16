from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.errors import AppError
from app.schemas.article import ArticleOut, MarkAllReadRequest
from app.schemas.common import OkResponse, Page
from app.services import articles as article_service
from app.services.articles import ArticleRow

router = APIRouter(prefix="/articles", tags=["articles"])


def _to_out(row: ArticleRow) -> ArticleOut:
    out = ArticleOut.model_validate(row.article)
    out.is_read = row.is_read
    out.is_saved = row.is_saved
    return out


@router.get("", response_model=Page[ArticleOut])
async def list_articles(
    user: CurrentUser,
    db: DbSession,
    folder: uuid.UUID | None = None,
    source: uuid.UUID | None = None,
    unread: bool | None = None,
    saved: bool | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> Page[ArticleOut]:
    page = await article_service.list_articles(
        db,
        user.id,
        folder=folder,
        source=source,
        unread=unread,
        saved=saved,
        q=q,
        cursor=cursor,
        limit=limit,
    )
    return Page(items=[_to_out(r) for r in page.rows], next_cursor=page.next_cursor)


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(article_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ArticleOut:
    row = await article_service.get_article(db, user.id, article_id)
    if row is None:
        raise AppError(404, "not_found", "Article not found.")
    return _to_out(row)


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


@router.post("/mark-all-read", response_model=OkResponse)
async def mark_all_read(body: MarkAllReadRequest, user: CurrentUser, db: DbSession) -> OkResponse:
    await article_service.mark_all_read(db, user.id, folder=body.folder_id, source=body.source_id)
    return OkResponse()
