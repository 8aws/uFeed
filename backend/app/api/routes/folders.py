from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.errors import not_implemented
from app.schemas.common import OkResponse
from app.schemas.folder import FolderCreate, FolderOut, FolderUpdate

router = APIRouter(prefix="/folders", tags=["folders"])


@router.get("", response_model=list[FolderOut])
async def list_folders() -> list[FolderOut]:
    raise not_implemented("folders.list")


@router.post("", response_model=FolderOut)
async def create_folder(body: FolderCreate) -> FolderOut:
    raise not_implemented("folders.create")


@router.patch("/{folder_id}", response_model=FolderOut)
async def update_folder(folder_id: uuid.UUID, body: FolderUpdate) -> FolderOut:
    raise not_implemented("folders.update")


@router.delete("/{folder_id}", response_model=OkResponse)
async def delete_folder(folder_id: uuid.UUID) -> OkResponse:
    raise not_implemented("folders.delete")
