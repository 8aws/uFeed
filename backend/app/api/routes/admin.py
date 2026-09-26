from __future__ import annotations

import uuid

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.api.errors import AppError
from app.core.roles import REFRESH_COOLDOWN_S, ROLES
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.admin import AdminSettings, AdminSettingsUpdate, AdminUserOut, AdminUserUpdate
from app.services import site as site_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_out(user: User, feeds: int) -> AdminUserOut:
    return AdminUserOut.model_validate(user).model_copy(update={"feeds": int(feeds or 0)})


def _settings_out(cfg: dict) -> AdminSettings:
    return AdminSettings(
        registration_open=cfg["registration_open"],
        default_role=cfg["default_role"],
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
        target.is_active = body.is_active
    await db.commit()
    await db.refresh(target)
    n = await db.scalar(
        select(func.count()).select_from(Subscription).where(Subscription.user_id == target.id)
    )
    return _user_out(target, n)
