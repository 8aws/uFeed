from __future__ import annotations

import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.errors import AppError
from app.schemas.common import OkResponse
from app.schemas.folder import FolderCreate, FolderOut, FolderUpdate
from app.services import folders as folder_service

router = APIRouter(prefix="/folders", tags=["folders"])


async def _get_owned(db: DbSession, user: CurrentUser, folder_id: uuid.UUID):
    folder = await folder_service.get_folder(db, user.id, folder_id)
    if folder is None:
        raise AppError(404, "not_found", "Folder not found.")
    return folder


@router.get("", response_model=list[FolderOut])
async def list_folders(user: CurrentUser, db: DbSession) -> list[FolderOut]:
    return await folder_service.list_folders(db, user.id)


@router.post("", response_model=FolderOut, status_code=201)
async def create_folder(body: FolderCreate, user: CurrentUser, db: DbSession) -> FolderOut:
    return await folder_service.create_folder(db, user.id, body.name)


@router.patch("/{folder_id}", response_model=FolderOut)
async def update_folder(
    folder_id: uuid.UUID, body: FolderUpdate, user: CurrentUser, db: DbSession
) -> FolderOut:
    folder = await _get_owned(db, user, folder_id)
    return await folder_service.update_folder(db, folder, name=body.name, position=body.position)


@router.delete("/{folder_id}", response_model=OkResponse)
async def delete_folder(folder_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    folder = await _get_owned(db, user, folder_id)
    await folder_service.delete_folder(db, folder)
    return OkResponse()
