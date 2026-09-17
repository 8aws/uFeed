from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.routes.articles import _to_out
from app.schemas.article import ArticleOut
from app.services import ai as ai_service
from app.services import articles as article_service

router = APIRouter(prefix="/foryou", tags=["foryou"])


@router.get("", response_model=list[ArticleOut])
async def get_for_you(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[ArticleOut]:
    arts = await ai_service.for_you(db, user.id, limit=limit)
    rows = await article_service.rows_for_ids(db, user.id, [a.id for a in arts])
    return [_to_out(r) for r in rows]
