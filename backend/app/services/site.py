"""Instance-wide settings (registration gate, default signup role)."""

from __future__ import annotations

import copy
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import DEFAULT_PLAN_LIMITS, DEFAULT_SIGNUP_ROLE, ROLES
from app.models.app_setting import AppSetting
from app.models.user import User

DEFAULTS: dict[str, Any] = {
    "registration_open": True,
    "default_role": DEFAULT_SIGNUP_ROLE,
    # Days of articles to keep (0 = forever); saved/favourites are always kept.
    "retention_days": 90,
    # Stage 1: deactivate non-admin accounts idle this many days (0 = never).
    "inactivity_days": 180,
    # Stage 2: delete deactivated accounts nobody reclaimed after this many
    # more days (0 = never delete).
    "dormant_delete_days": 180,
}


async def get_settings(db: AsyncSession) -> dict[str, Any]:
    rows = (await db.execute(select(AppSetting))).scalars().all()
    out = dict(DEFAULTS)
    out.update({r.key: r.value for r in rows if r.key in DEFAULTS})
    if out["default_role"] not in ROLES:
        out["default_role"] = DEFAULT_SIGNUP_ROLE
    return out


async def update_settings(db: AsyncSession, values: dict[str, Any]) -> dict[str, Any]:
    for key, value in values.items():
        if key not in DEFAULTS:
            continue
        row = await db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value
    await db.commit()
    return await get_settings(db)


async def user_count(db: AsyncSession) -> int:
    return int((await db.execute(select(func.count()).select_from(User))).scalar_one())


async def get_internal(db: AsyncSession, key: str) -> Any:
    """Read a system-maintained value (e.g. last purge result)."""
    row = await db.get(AppSetting, key)
    return row.value if row else None


async def set_internal(db: AsyncSession, key: str, value: Any) -> None:
    """Write a system-maintained value that admins can't edit directly."""
    row = await db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    await db.commit()


async def plan_limits(db: AsyncSession) -> dict[str, dict[str, Any]]:
    """Per-role limits: code defaults overridden by what admins saved."""
    out = copy.deepcopy(DEFAULT_PLAN_LIMITS)
    saved = await get_internal(db, "plan_limits") or {}
    for role, limits in saved.items():
        if role in out and isinstance(limits, dict):
            out[role].update({k: v for k, v in limits.items() if k in out[role]})
    return out


async def limits_for(db: AsyncSession, role: str) -> dict[str, Any]:
    plans = await plan_limits(db)
    return plans.get(role, plans["free"])


async def save_plan_limits(db: AsyncSession, plans: dict[str, dict[str, Any]]) -> None:
    await set_internal(db, "plan_limits", plans)
