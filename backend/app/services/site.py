"""Instance-wide settings (registration gate, default signup role)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import DEFAULT_SIGNUP_ROLE, ROLES
from app.models.app_setting import AppSetting
from app.models.user import User

DEFAULTS: dict[str, Any] = {
    "registration_open": True,
    "default_role": DEFAULT_SIGNUP_ROLE,
    # Days of articles to keep (0 = forever); saved/favourites are always kept.
    "retention_days": 90,
    # Delete non-admin accounts idle this many days (0 = never).
    "inactivity_days": 180,
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
