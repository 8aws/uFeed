from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.errors import AppError
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.schemas.common import OkResponse
from app.services import api_keys as api_key_service
from app.services import site as site_service

router = APIRouter(prefix="/keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(user: CurrentUser, db: DbSession) -> list[ApiKeyOut]:
    return await api_key_service.list_api_keys(db, user.id)


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_key(body: ApiKeyCreate, user: CurrentUser, db: DbSession) -> ApiKeyCreated:
    max_keys = (await site_service.limits_for(db, user.role))["max_api_keys"]
    if max_keys is not None:
        active = [k for k in await api_key_service.list_api_keys(db, user.id) if not k.revoked_at]
        if len(active) >= max_keys:
            raise AppError(403, "plan_limit_keys", f"Your plan allows up to {max_keys} API keys.")
    key, plaintext = await api_key_service.create_api_key(db, user.id, body.name, body.scopes)
    return ApiKeyCreated.model_validate({**key.__dict__, "key": plaintext})


@router.delete("/{key_id}", response_model=OkResponse)
async def revoke_key(key_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    revoked = await api_key_service.revoke_api_key(db, user.id, key_id)
    if not revoked:
        raise AppError(404, "not_found", "API key not found or already revoked.")
    return OkResponse()
