from __future__ import annotations

import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
)
from app.models.user import User
from app.schemas.auth import Tokens


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, email: str, password: str, locale: str, role: str = "free"
) -> User:
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        locale=locale,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_profile(
    db: AsyncSession,
    user: User,
    *,
    fields: set[str],
    locale: str | None = None,
    display_name: str | None = None,
    digest_hour: int | None = None,
) -> User:
    """Apply only the provided fields (fields = the keys actually sent)."""
    if "locale" in fields and locale is not None:
        user.locale = locale
    if "display_name" in fields:
        cleaned = (display_name or "").strip()
        user.display_name = cleaned or None
    if "digest_hour" in fields:
        user.digest_hour = digest_hour
        # If today's hour has already gone, the first one goes out tomorrow.
        now = datetime.now(ZoneInfo(settings.digest_tz))
        user.digest_sent_on = (
            now.date() if digest_hour is not None and now.hour >= digest_hour else None
        )
    await db.commit()
    await db.refresh(user)
    return user


def tokens_for(user: User) -> Tokens:
    sub = str(user.id)
    return Tokens(
        access_token=create_access_token(sub, user.token_version),
        refresh_token=create_refresh_token(sub, user.token_version),
    )


def temporary_password() -> str:
    return secrets.token_urlsafe(9)


async def set_password(
    db: AsyncSession, user: User, password: str, *, must_change: bool = False
) -> User:
    """Set a new password and invalidate every existing session."""
    user.password_hash = hash_password(password)
    user.token_version += 1
    user.must_change_password = must_change
    await db.commit()
    await db.refresh(user)
    return user
