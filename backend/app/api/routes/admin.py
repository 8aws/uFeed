from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import func, select, text

from app.api.deps import AdminUser, DbSession
from app.api.errors import AppError
from app.api.routes.sources import health_out
from app.core.config import settings
from app.core.roles import REFRESH_COOLDOWN_S, ROLES
from app.models.article import Article
from app.models.ban import Ban
from app.models.source import Source
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.admin import (
    AdminSettings,
    AdminSettingsUpdate,
    AdminUserOut,
    AdminUserUpdate,
    BanCreate,
    BanOut,
    BanRequest,
    Maintenance,
    SuspendRequest,
    TemporaryPassword,
)
from app.schemas.common import OkResponse
from app.schemas.source import SourceHealthOut, SourcePauseRequest
from app.services import auth as auth_service
from app.services import moderation, source_health
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


def _settings_out(cfg: dict) -> AdminSettings:
    return AdminSettings(
        registration_open=cfg["registration_open"],
        default_role=cfg["default_role"],
        retention_days=cfg["retention_days"],
        inactivity_days=cfg["inactivity_days"],
        dormant_delete_days=cfg["dormant_delete_days"],
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
    feeds = _feeds_subquery()
    rows = (
        await db.execute(
            select(User, func.coalesce(feeds.c.n, 0), moderation.last_activity_expr())
            .outerjoin(feeds, feeds.c.user_id == User.id)
            .order_by(User.created_at)
        )
    ).all()
    now = moderation.now()
    bans = {
        b.email: b
        for b in (await db.execute(select(Ban))).scalars()
        if b.until is None or b.until > now
    }
    return [_user_out(u, n, act, bans.get(u.email)) for u, n, act in rows]


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


# --- Feed health ----------------------------------------------------------------


@router.get("/sources", response_model=list[SourceHealthOut])
async def admin_sources(_: AdminUser, db: DbSession) -> list[SourceHealthOut]:
    """Every feed on the instance, problems first, with subscriber counts."""
    return [health_out(r) for r in await source_health.for_admin(db)]


@router.patch("/sources/{source_id}", response_model=OkResponse)
async def pause_source(
    source_id: uuid.UUID, body: SourcePauseRequest, _: AdminUser, db: DbSession
) -> OkResponse:
    """Pause polling of a dead feed (or resume it, retrying soon)."""
    src = await db.get(Source, source_id)
    if src is None:
        raise AppError(404, "not_found", "Source not found.")
    await source_health.set_paused(db, src, body.paused)
    return OkResponse()


@router.post("/sources/delete-orphans")
async def delete_orphan_sources(_: AdminUser, db: DbSession) -> dict[str, int]:
    """Remove feeds nobody follows (keeps any with saved/favourite articles)."""
    return {"deleted": await source_health.delete_orphans(db)}
