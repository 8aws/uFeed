from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.errors import not_implemented
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyOut
from app.schemas.common import OkResponse

router = APIRouter(prefix="/keys", tags=["api-keys"])


@router.get("", response_model=list[ApiKeyOut])
async def list_keys() -> list[ApiKeyOut]:
    raise not_implemented("keys.list")


@router.post("", response_model=ApiKeyCreated)
async def create_key(body: ApiKeyCreate) -> ApiKeyCreated:
    raise not_implemented("keys.create")


@router.delete("/{key_id}", response_model=OkResponse)
async def revoke_key(key_id: uuid.UUID) -> OkResponse:
    raise not_implemented("keys.revoke")
