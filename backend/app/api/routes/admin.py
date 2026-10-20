from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Query
from sqlalchemy import func, select, text

from app.api.deps import AdminUser, DbSession
from app.api.errors import AppError
from app.core.config import settings
from app.core.roles import ROLES, Role
from app.models.article import Article
from app.models.ban import Ban
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.admin import (
    AdminSettings,
    AdminSettingsUpdate,
    AdminSummary,
    AdminUserOut,
    AdminUserPage,
    AdminUserUpdate,
    BanCreate,
    BanOut,
    BanRequest,
    GuestPurge,
    GuestPurgeResult,
    Maintenance,
    PlanLimits,
    SuspendRequest,
    TemporaryPassword,
)
from app.schemas.common import OkResponse
from app.services import admin_users, metrics, moderation
from app.services import auth as auth_service
from app.services import retention as retention_service
from app.services import site as site_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _user_out(user: User, feeds: int, activity=None, ban: Ban | None = None) -> AdminUserOut:
    return AdminUserOut.model_validate(user).model_copy(
        update={
            "feeds": int(feeds or 0),
            "last_activity_at": activity,
            "banned": ban is not None,
            "ban_until": ban.until if ban else None,
        }
    )


def _feeds_subquery():
    return (
        select(Subscription.user_id, func.count().label("n"))
        .group_by(Subscription.user_id)
        .subquery()
    )


async def _user_row(db, user: User) -> AdminUserOut:
    """Admin view of one user (feeds, last activity, active ban)."""
    feeds = _feeds_subquery()
    n, activity = (
        await db.execute(
            select(func.coalesce(feeds.c.n, 0), moderation.last_activity_expr())
            .select_from(User)
            .outerjoin(feeds, feeds.c.user_id == User.id)
            .where(User.id == user.id)
        )
    ).one()
    return _user_out(user, n, activity, await moderation.active_ban(db, user.email))


async def _target(db, user_id: uuid.UUID, admin: User) -> User:
    target = await db.get(User, user_id)
    if target is None:
        raise AppError(404, "not_found", "User not found.")
    if target.id == admin.id:
        raise AppError(400, "cannot_modify_self", "You can't do that to your own account.")
    return target


def _settings_out(cfg: dict, plans: dict) -> AdminSettings:
    return AdminSettings(
        registration_open=cfg["registration_open"],
        default_role=cfg["default_role"],
        retention_days=cfg["retention_days"],
        inactivity_days=cfg["inactivity_days"],
        dormant_delete_days=cfg["dormant_delete_days"],
        contact_email=cfg.get("contact_email") or "",
        roles=list(ROLES),
        refresh_cooldown_s={r: int(p["refresh_cooldown_s"]) for r, p in plans.items()},
        plan_limits=plans,
    )


@router.get("/settings", response_model=AdminSettings)
async def get_settings(_: AdminUser, db: DbSession) -> AdminSettings:
    return _settings_out(await site_service.get_settings(db), await site_service.plan_limits(db))


@router.patch("/settings", response_model=AdminSettings)
async def update_settings(body: AdminSettingsUpdate, _: AdminUser, db: DbSession) -> AdminSettings:
    values = body.model_dump(exclude_none=True)
    cfg = await site_service.update_settings(db, values)
    return _settings_out(cfg, await site_service.plan_limits(db))


@router.put("/plans", response_model=AdminSettings)
async def update_plans(body: dict[Role, PlanLimits], _: AdminUser, db: DbSession) -> AdminSettings:
    """Replace the limits of the given plans (others keep their values)."""
    plans = await site_service.plan_limits(db)
    for role, limits in body.items():
        plans[role] = limits.model_dump()
    await site_service.save_plan_limits(db, plans)
    return _settings_out(await site_service.get_settings(db), plans)


@router.get("/users", response_model=AdminUserPage)
async def list_users(
    _: AdminUser,
    db: DbSession,
    q: str | None = Query(default=None, max_length=100, description="email or name contains"),
    role: str | None = Query(default=None, max_length=16),
    status: Literal["active", "disabled", "suspended", "banned", "dormant"] | None = None,
    guests: Literal["hide", "only", "all"] = "hide",
    inactive_days: int | None = Query(default=None, ge=1, le=3650),
    sort: Literal["created", "activity", "feeds", "email"] = "created",
    order: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> AdminUserPage:
    """One page of users, filtered and sorted by the database. Guests are left
    out unless asked for (`guests=all|only`): there can be thousands."""
    rows, total, bans = await admin_users.page(
        db,
        q=q,
        role=role,
        status=status,
        guests=guests,
        inactive_days=inactive_days,
        sort=sort,
        descending=order == "desc",
        limit=limit,
        offset=offset,
    )
    return AdminUserPage(
        items=[_user_out(r.user, r.feeds, r.activity, bans.get(r.user.email)) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/users/summary", response_model=AdminSummary)
async def users_summary(_: AdminUser, db: DbSession) -> AdminSummary:
    """Totals for the dashboard (counted in the database, no lists)."""
    return AdminSummary(**await admin_users.summary(db))


@router.post("/guests/purge", response_model=GuestPurgeResult)
async def purge_guests(body: GuestPurge, _: AdminUser, db: DbSession) -> GuestPurgeResult:
    """Delete the guest profiles idle for `days` or more (what the nightly
    clean-up does, with the number of days you choose)."""
    return GuestPurgeResult(deleted=await moderation.delete_idle_guests(db, body.days))


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
    return await _user_row(db, target)


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


@router.get("/metrics")
async def resource_metrics(_: AdminUser, db: DbSession, days: int = 7) -> dict:
    """Resource monitor: load/memory/storage/users samples and daily usage of
    the heavy features (voice, translation, AI summaries)."""
    return await metrics.series(db, max(1, min(days, 180)))


@router.get("/maintenance", response_model=Maintenance)
async def maintenance(_: AdminUser, db: DbSession) -> Maintenance:
    cfg = await site_service.get_settings(db)
    size = await db.scalar(text("SELECT pg_database_size(current_database())"))
    count = await db.scalar(select(func.count()).select_from(Article))
    return Maintenance(
        retention_days=cfg["retention_days"],
        last_purge=await site_service.get_internal(db, "last_purge"),
        inactivity_days=cfg["inactivity_days"],
        dormant_delete_days=cfg["dormant_delete_days"],
        last_inactive_cleanup=await site_service.get_internal(db, "last_inactive_cleanup"),
        db_size_bytes=int(size or 0),
        articles=int(count or 0),
        backups=_backup_status(),
    )


@router.post("/retention/run", response_model=Maintenance)
async def run_retention_now(admin: AdminUser, db: DbSession) -> Maintenance:
    """Apply the retention policy now instead of waiting for the nightly run."""
    await retention_service.run_retention(db)
    return await maintenance(admin, db)


# --- Moderation ---------------------------------------------------------------


@router.post("/users/{user_id}/suspend", response_model=AdminUserOut)
async def suspend_user(
    user_id: uuid.UUID, body: SuspendRequest, admin: AdminUser, db: DbSession
) -> AdminUserOut:
    """Temporarily block an account (signs it out; lifts by itself)."""
    target = await _target(db, user_id, admin)
    await moderation.suspend(db, target, body.days)
    return await _user_row(db, target)


@router.delete("/users/{user_id}/suspend", response_model=AdminUserOut)
async def unsuspend_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> AdminUserOut:
    target = await _target(db, user_id, admin)
    await moderation.lift(db, target)
    return await _user_row(db, target)


@router.post("/users/{user_id}/reactivate", response_model=AdminUserOut)
async def reactivate_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> AdminUserOut:
    """Undo a deactivation for inactivity (stops the pending deletion)."""
    target = await _target(db, user_id, admin)
    await moderation.reactivate(db, target)
    return await _user_row(db, target)


@router.post("/users/{user_id}/ban", response_model=AdminUserOut)
async def ban_user(
    user_id: uuid.UUID, body: BanRequest, admin: AdminUser, db: DbSession
) -> AdminUserOut:
    """Ban the account's email (temporary or permanent); blocks re-registering."""
    target = await _target(db, user_id, admin)
    await moderation.ban_email(db, target.email, body.days, body.reason, admin)
    await db.refresh(target)
    return await _user_row(db, target)


@router.delete("/users/{user_id}/ban", response_model=AdminUserOut)
async def unban_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> AdminUserOut:
    target = await _target(db, user_id, admin)
    await moderation.unban_email(db, target.email)
    await db.refresh(target)
    return await _user_row(db, target)


@router.delete("/users/{user_id}", response_model=OkResponse)
async def delete_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> OkResponse:
    """Delete an account and all its data. Admins must be demoted first."""
    target = await _target(db, user_id, admin)
    if target.role == "admin":
        raise AppError(400, "cannot_delete_admin", "Demote the admin before deleting it.")
    await moderation.delete_user(db, target)
    return OkResponse()


@router.get("/bans", response_model=list[BanOut])
async def list_bans(_: AdminUser, db: DbSession) -> list[BanOut]:
    rows = (await db.execute(select(Ban).order_by(Ban.created_at.desc()))).scalars()
    return [BanOut.model_validate(b) for b in rows]


@router.post("/bans", response_model=BanOut, status_code=201)
async def create_ban(body: BanCreate, admin: AdminUser, db: DbSession) -> BanOut:
    """Ban an email even if it has no account yet (prevents signing up)."""
    if body.email.lower() == admin.email:
        raise AppError(400, "cannot_modify_self", "You can't ban yourself.")
    ban = await moderation.ban_email(db, body.email, body.days, body.reason, admin)
    return BanOut.model_validate(ban)


@router.delete("/bans/{ban_id}", response_model=OkResponse)
async def delete_ban(ban_id: uuid.UUID, _: AdminUser, db: DbSession) -> OkResponse:
    ban = await db.get(Ban, ban_id)
    if ban is None:
        raise AppError(404, "not_found", "Ban not found.")
    await moderation.unban_email(db, ban.email)
    return OkResponse()


@router.post("/inactivity/run", response_model=Maintenance)
async def run_inactivity_now(admin: AdminUser, db: DbSession) -> Maintenance:
    """Apply the inactivity policy now instead of waiting for the nightly run."""
    await moderation.run_inactivity_cleanup(db)
    return await maintenance(admin, db)
