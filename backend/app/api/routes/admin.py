from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.api.deps import AdminUser, DbSession
from app.api.errors import AppError
from app.core.config import settings
from app.core.roles import REFRESH_COOLDOWN_S, ROLES
from app.models.article import Article
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.admin import (
    AdminSettings,
    AdminSettingsUpdate,
    AdminUserOut,
    AdminUserUpdate,
    Maintenance,
    TemporaryPassword,
)
from app.services import auth as auth_service
from app.services import retention as retention_service
from app.services import site as site_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_out(user: User, feeds: int) -> AdminUserOut:
    return AdminUserOut.model_validate(user).model_copy(update={"feeds": int(feeds or 0)})


def _settings_out(cfg: dict) -> AdminSettings:
    return AdminSettings(
        registration_open=cfg["registration_open"],
        default_role=cfg["default_role"],
        retention_days=cfg["retention_days"],
        roles=list(ROLES),
        refresh_cooldown_s=dict(REFRESH_COOLDOWN_S),
    )


@router.get("/settings", response_model=AdminSettings)
async def get_settings(_: AdminUser, db: DbSession) -> AdminSettings:
    return _settings_out(await site_service.get_settings(db))


@router.patch("/settings", response_model=AdminSettings)
async def update_settings(body: AdminSettingsUpdate, _: AdminUser, db: DbSession) -> AdminSettings:
    values = body.model_dump(exclude_none=True)
    return _settings_out(await site_service.update_settings(db, values))


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(_: AdminUser, db: DbSession) -> list[AdminUserOut]:
    feeds = (
        select(Subscription.user_id, func.count().label("n"))
        .group_by(Subscription.user_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(User, func.coalesce(feeds.c.n, 0))
            .outerjoin(feeds, feeds.c.user_id == User.id)
            .order_by(User.created_at)
        )
    ).all()
    return [_user_out(u, n) for u, n in rows]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: uuid.UUID, body: AdminUserUpdate, admin: AdminUser, db: DbSession
) -> AdminUserOut:
    target = await db.get(User, user_id)
    if target is None:
        raise AppError(404, "not_found", "User not found.")
    # Never let an admin lock themselves out (keeps at least one admin).
    if target.id == admin.id and (
        (body.role is not None and body.role != "admin") or body.is_active is False
    ):
        raise AppError(400, "cannot_modify_self", "You can't demote or disable your own account.")
    if body.role is not None:
        target.role = body.role
    if body.is_active is not None:
        if target.is_active and not body.is_active:
            target.token_version += 1  # sign the account out everywhere
        target.is_active = body.is_active
    await db.commit()
    await db.refresh(target)
    n = await db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.user_id == target.id)
    )
    return _user_out(target, n)


@router.post("/users/{user_id}/reset-password", response_model=TemporaryPassword)
async def reset_password(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> TemporaryPassword:
    """Set a random temporary password (shown once) and sign the user out."""
    target = await db.get(User, user_id)
    if target is None:
        raise AppError(404, "not_found", "User not found.")
    if target.id == admin.id:
        raise AppError(400, "cannot_modify_self", "Use Settings to change your own password.")
    temp = auth_service.temporary_password()
    await auth_service.set_password(db, target, temp, must_change=True)
    return TemporaryPassword(temporary_password=temp)


def _backup_status() -> dict | None:
    """Written by scripts/backup.sh; mounted read-only into the backend."""
    path = Path(settings.backups_dir) / "status.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


@router.get("/maintenance", response_model=Maintenance)
async def maintenance(_: AdminUser, db: DbSession) -> Maintenance:
    cfg = await site_service.get_settings(db)
    size = await db.scalar(text("SELECT pg_database_size(current_database())"))
    count = await db.scalar(select(func.count()).select_from(Article))
    return Maintenance(
        retention_days=cfg["retention_days"],
        last_purge=await site_service.get_internal(db, "last_purge"),
        db_size_bytes=int(size or 0),
        articles=int(count or 0),
        backups=_backup_status(),
    )


@router.post("/retention/run", response_model=Maintenance)
async def run_retention_now(admin: AdminUser, db: DbSession) -> Maintenance:
    """Apply the retention policy now instead of waiting for the nightly run."""
    await retention_service.run_retention(db)
    return await maintenance(admin, db)
