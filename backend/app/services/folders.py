from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder


async def list_folders(db: AsyncSession, user_id: uuid.UUID) -> list[Folder]:
    result = await db.execute(
        select(Folder).where(Folder.user_id == user_id).order_by(Folder.position, Folder.name)
    )
    return list(result.scalars().all())


async def get_folder(db: AsyncSession, user_id: uuid.UUID, folder_id: uuid.UUID) -> Folder | None:
    result = await db.execute(
        select(Folder).where(Folder.id == folder_id, Folder.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_folder(db: AsyncSession, user_id: uuid.UUID, name: str) -> Folder:
    folder = Folder(user_id=user_id, name=name)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


async def update_folder(
    db: AsyncSession,
    folder: Folder,
    *,
    name: str | None = None,
    position: int | None = None,
) -> Folder:
    if name is not None:
        folder.name = name
    if position is not None:
        folder.position = position
    await db.commit()
    await db.refresh(folder)
    return folder


async def delete_folder(db: AsyncSession, folder: Folder) -> None:
    # Subscriptions keep existing; their folder_id is set NULL by the FK rule.
    await db.delete(folder)
    await db.commit()
