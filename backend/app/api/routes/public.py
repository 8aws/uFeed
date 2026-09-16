from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.api.deps import ApiKeyPrincipal, DbSession
from app.api.errors import AppError
from app.api.routes.articles import _to_out as _article_out
from app.api.routes.sources import _to_out as _sub_out
from app.schemas.article import ArticleOut
from app.schemas.common import Page
from app.schemas.source import SubscriptionOut
from app.services import articles as article_service
from app.services import subscriptions as sub_service

# Public, read-only API. Authenticated via API key (X-API-Key header);
# results are scoped to the key owner's account.
router = APIRouter(prefix="/v1", tags=["public"])


@router.get("/sources", response_model=list[SubscriptionOut])
async def public_list_sources(principal: ApiKeyPrincipal, db: DbSession) -> list[SubscriptionOut]:
    rows = await sub_service.list_subscriptions(db, principal.user_id)
    return [_sub_out(r) for r in rows]


@router.get("/articles", response_model=Page[ArticleOut])
async def public_list_articles(
    principal: ApiKeyPrincipal,
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
        principal.user_id,
        folder=folder,
        source=source,
        unread=unread,
        saved=saved,
        q=q,
        cursor=cursor,
        limit=limit,
    )
    return Page(items=[_article_out(r) for r in page.rows], next_cursor=page.next_cursor)


@router.get("/articles/{article_id}", response_model=ArticleOut)
async def public_get_article(
    article_id: uuid.UUID, principal: ApiKeyPrincipal, db: DbSession
) -> ArticleOut:
    row = await article_service.get_article(db, principal.user_id, article_id)
    if row is None:
        raise AppError(404, "not_found", "Article not found.")
    return _article_out(row)
