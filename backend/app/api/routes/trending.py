from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.routes.articles import _to_out
from app.schemas.article import TrendingItem
from app.services import articles as article_service

router = APIRouter(prefix="/trending", tags=["trending"])


@router.get("", response_model=list[TrendingItem])
async def get_trending(
    user: CurrentUser,
    db: DbSession,
    window_hours: int = Query(default=48, ge=1, le=720),
    limit: int = Query(default=8, ge=1, le=30),
) -> list[TrendingItem]:
    rows = await article_service.trending(db, user.id, window_hours=window_hours, limit=limit)
    return [
        TrendingItem(
            article=_to_out(r.row),
            readers=r.readers,
            avg_completion=r.avg_completion,
            avg_dwell_ms=r.avg_dwell_ms,
            score=r.score,
        )
        for r in rows
    ]
