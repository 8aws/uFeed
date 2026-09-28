from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.errors import AppError
from app.schemas.common import OkResponse
from app.schemas.source import MutedKeywordIn, MutedKeywordOut
from app.services import filters as filters_service

router = APIRouter(prefix="/filters", tags=["filters"])


@router.get("/keywords", response_model=list[MutedKeywordOut])
async def list_keywords(user: CurrentUser, db: DbSession) -> list[MutedKeywordOut]:
    rows = await filters_service.list_keywords(db, user.id)
    return [MutedKeywordOut.model_validate(r) for r in rows]


@router.post("/keywords", response_model=MutedKeywordOut, status_code=201)
async def add_keyword(body: MutedKeywordIn, user: CurrentUser, db: DbSession) -> MutedKeywordOut:
    """Hide articles whose title or summary contains this word or phrase."""
    row = await filters_service.add_keyword(db, user.id, body.keyword)
    if row is None:
        raise AppError(
            400, "keyword_rejected", f"Empty keyword or limit of {filters_service.MAX_KEYWORDS}."
        )
    return MutedKeywordOut.model_validate(row)


@router.delete("/keywords/{keyword_id}", response_model=OkResponse)
async def remove_keyword(keyword_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    if not await filters_service.remove_keyword(db, user.id, keyword_id):
        raise AppError(404, "not_found", "Keyword not found.")
    return OkResponse()
