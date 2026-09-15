from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.api.deps import ApiKeyPrincipal
from app.api.errors import not_implemented
from app.schemas.article import ArticleOut
from app.schemas.common import Page
from app.schemas.source import SubscriptionOut

# Public, read-only API. Authenticated via API key (X-API-Key header).
# The data logic lands in WS3; here the endpoints already enforce auth.
router = APIRouter(prefix="/v1", tags=["public"])


@router.get("/sources", response_model=list[SubscriptionOut])
async def public_list_sources(principal: ApiKeyPrincipal) -> list[SubscriptionOut]:
    raise not_implemented("public.sources.list")


@router.get("/articles", response_model=Page[ArticleOut])
async def public_list_articles(
    principal: ApiKeyPrincipal,
    folder: uuid.UUID | None = None,
    source: uuid.UUID | None = None,
    unread: bool | None = None,
    saved: bool | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> Page[ArticleOut]:
    raise not_implemented("public.articles.list")


@router.get("/articles/{article_id}", response_model=ArticleOut)
async def public_get_article(article_id: uuid.UUID, principal: ApiKeyPrincipal) -> ArticleOut:
    raise not_implemented("public.articles.get")
