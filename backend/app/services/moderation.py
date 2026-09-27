"""Account moderation: suspensions, bans, deletion and inactivity clean-up."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionLocal
from app.models.api_key import ApiKey
from app.models.ban import Ban
from app.models.user import User
from app.services import site as site_service

log = logging.getLogger("ufeed.moderation")

SEEN_RESOLUTION = timedelta(hours=1)  # don't write last_seen_at on every request


def now() -> datetime:
    return datetime.now(UTC)


def is_suspended(user: User) -> bool:
    return user.suspended_until is not None and user.suspended_until > now()


async def active_ban(db: AsyncSession, email: str) -> Ban | None:
    stmt = (
        select(Ban)
        .where(Ban.email == email.lower(), or_(Ban.until.is_(None), Ban.until > now()))
        .order_by(Ban.until.desc().nulls_first())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def touch(db: AsyncSession, user: User) -> None:
    """Record activity (at most once per SEEN_RESOLUTION)."""
    if user.last_seen_at is None or now() - user.last_seen_at > SEEN_RESOLUTION:
        user.last_seen_at = now()
        await db.commit()


def _signout(user: User) -> None:
    user.token_version += 1


async def suspend(db: AsyncSession, user: User, days: int) -> User:
    user.suspended_until = now() + timedelta(days=days)
    _signout(user)
    await db.commit()
    return user


async def lift(db: AsyncSession, user: User) -> User:
    """End a temporary suspension (indefinite deactivation is `is_active`)."""
    user.suspended_until = None
    await db.commit()
    return user


async def ban_email(
    db: AsyncSession, email: str, days: int | None, reason: str | None, by: User | None
) -> Ban:
    """Ban an email (and its account, if any). days=None -> permanent."""
    email = email.lower().strip()
    until = now() + timedelta(days=days) if days else None
    await db.execute(delete(Ban).where(Ban.email == email))
    ban = Ban(email=email, until=until, reason=reason, created_by=by.id if by else None)
    db.add(ban)
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is not None:
        if until is None:
            user.is_active = False
        else:
            user.suspended_until = until
        _signout(user)
    await db.commit()
    await db.refresh(ban)
    return ban


async def unban_email(db: AsyncSession, email: str) -> None:
    email = email.lower().strip()
    await db.execute(delete(Ban).where(Ban.email == email))
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is not None:
        user.suspended_until = None
        user.is_active = True
    await db.commit()


async def delete_user(db: AsyncSession, user: User) -> None:
    """Remove an account and everything it owns (FKs cascade)."""
    await db.delete(user)
    await db.commit()


def last_activity_expr():
    """Latest of: web activity, API-key use, account creation."""
    keys = select(func.max(ApiKey.last_used_at)).where(ApiKey.user_id == User.id).scalar_subquery()
    return func.greatest(User.last_seen_at, keys, User.created_at)


def is_dormant(user: User) -> bool:
    return user.dormant_since is not None


async def reactivate(db: AsyncSession, user: User) -> User:
    """Reclaim an account deactivated for inactivity (sign-in or API use)."""
    user.dormant_since = None
    user.last_seen_at = now()
    await db.commit()
    return user


def active_user_ids(window: timedelta):
    """Users active (web or API key) within `window` and not deactivated."""
    return select(User.id).where(
        User.is_active.is_(True),
        User.dormant_since.is_(None),
        last_activity_expr() > now() - window,
    )


async def deactivate_inactive(db: AsyncSession, days: int) -> list[str]:
    """Stage 1: mark non-admin accounts idle for `days` as dormant (0 = never)."""
    if days <= 0:
        return []
    cutoff = now() - timedelta(days=days)
    idle = (
        (
            await db.execute(
                select(User).where(
                    User.role != "admin",
                    User.dormant_since.is_(None),
                    last_activity_expr() < cutoff,
                )
            )
        )
        .scalars()
        .all()
    )
    for user in idle:
        user.dormant_since = now()
        _signout(user)
    await db.commit()
    return [u.email for u in idle]


async def delete_dormant(db: AsyncSession, days: int) -> list[str]:
    """Stage 2: delete accounts dormant for `days` that nobody reclaimed."""
    if days <= 0:
        return []
    cutoff = now() - timedelta(days=days)
    gone = (
        (await db.execute(select(User).where(User.role != "admin", User.dormant_since < cutoff)))
        .scalars()
        .all()
    )
    for user in gone:
        await db.delete(user)
    await db.commit()
    return [u.email for u in gone]


async def run_inactivity_cleanup(db: AsyncSession | None = None) -> dict[str, Any]:
    if db is None:
        async with SessionLocal() as session:
            return await run_inactivity_cleanup(session)
    cfg = await site_service.get_settings(db)
    deleted = await delete_dormant(db, int(cfg["dormant_delete_days"]))
    deactivated = await deactivate_inactive(db, int(cfg["inactivity_days"]))
    result = {
        "days": int(cfg["inactivity_days"]),
        "delete_days": int(cfg["dormant_delete_days"]),
        "deactivated_users": len(deactivated),
        "deleted_users": len(deleted),
        "at": now().isoformat(),
    }
    await site_service.set_internal(db, "last_inactive_cleanup", result)
    log.info("inactivity clean-up: %s", result)
    return result
