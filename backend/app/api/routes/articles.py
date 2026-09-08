from __future__ import annotations

import uuid

from fastapi import APIRouter, Query

from app.api.errors import not_implemented
from app.schemas.article import ArticleOut, MarkAllReadRequest
from app.schemas.common import OkResponse, Page

router = APIRouter(prefix="/articles", tags=["articles"])


@router.get("", response_model=Page[ArticleOut])
async def list_articles(
    folder: uuid.UUID | None = None,
    source: uuid.UUID | None = None,
    unread: bool | None = None,
    saved: bool | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> Page[ArticleOut]:
    raise not_implemented("articles.list")


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(article_id: uuid.UUID) -> ArticleOut:
    raise not_implemented("articles.get")


@router.post("/{article_id}/read", response_model=OkResponse)
async def mark_read(article_id: uuid.UUID) -> OkResponse:
    raise not_implemented("articles.read")


@router.delete("/{article_id}/read", response_model=OkResponse)
async def mark_unread(article_id: uuid.UUID) -> OkResponse:
    raise not_implemented("articles.unread")


@router.post("/{article_id}/save", response_model=OkResponse)
async def mark_saved(article_id: uuid.UUID) -> OkResponse:
    raise not_implemented("articles.save")


@router.delete("/{article_id}/save", response_model=OkResponse)
async def mark_unsaved(article_id: uuid.UUID) -> OkResponse:
    raise not_implemented("articles.unsave")


@router.post("/mark-all-read", response_model=OkResponse)
async def mark_all_read(body: MarkAllReadRequest) -> OkResponse:
    raise not_implemented("articles.mark_all_read")
