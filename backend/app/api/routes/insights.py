from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.api.routes.articles import _to_out
from app.schemas.article import Insights, RankedArticle
from app.services import articles as article_service
from app.services.articles import RankedRow

router = APIRouter(prefix="/insights", tags=["insights"])


def _rank(r: RankedRow) -> RankedArticle:
    return RankedArticle(
        article=_to_out(r.row),
        readers=r.readers,
        quality=r.quality,
        saves=r.saves,
        favorites=r.favorites,
        opens=r.opens,
        score=r.score,
    )


@router.get("", response_model=Insights)
async def get_insights(
    user: CurrentUser,
    db: DbSession,
    window_hours: int = Query(default=48, ge=1, le=720),
    limit: int = Query(default=12, ge=1, le=30),
) -> Insights:
    ins = await article_service.insights(db, user.id, window_hours=window_hours, limit=limit)
    return Insights(
        trending_now=[_rank(r) for r in ins.trending_now],
        top=[_rank(r) for r in ins.top],
        most_saved=[_rank(r) for r in ins.most_saved],
        deep_reads=[_rank(r) for r in ins.deep_reads],
        hidden_gems=[_rank(r) for r in ins.hidden_gems],
    )
