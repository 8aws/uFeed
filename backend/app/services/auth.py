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


# Guests have no real address: this one never receives anything (example.org is
# reserved, and nothing is sent to guests anyway).
GUEST_DOMAIN = "guest.example.org"


async def create_guest(db: AsyncSession, locale: str) -> User:
    """An account for "continue without an account": no personal data, an
    address and password nobody knows, and only the device's tokens to open it."""
    user = User(
        email=f"guest-{secrets.token_hex(10)}@{GUEST_DOMAIN}",
        password_hash=hash_password(secrets.token_urlsafe(32)),
        locale=locale,
        role="guest",
        is_guest=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def upgrade_guest(db: AsyncSession, user: User, email: str, password: str, role: str) -> User:
    """Give a guest real credentials and a regular plan; its feeds and saved
    articles stay. Other sessions (there are none but this device) end."""
    user.email = email.lower()
    user.password_hash = hash_password(password)
    user.role = role
    user.is_guest = False
    user.token_version += 1
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
    digest_days: int | None = None,
) -> User:
    """Apply only the provided fields (fields = the keys actually sent)."""
    if "locale" in fields and locale is not None:
        user.locale = locale
    if "display_name" in fields:
        cleaned = (display_name or "").strip()
        user.display_name = cleaned or None
    if "digest_days" in fields and digest_days is not None:
        user.digest_days = digest_days
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
