from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, email: str, password: str, locale: str) -> User:
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        locale=locale,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def update_profile(
    db: AsyncSession,
    user: User,
    *,
    fields: set[str],
    locale: str | None = None,
    display_name: str | None = None,
) -> User:
    """Apply only the provided fields (fields = the keys actually sent)."""
    if "locale" in fields and locale is not None:
        user.locale = locale
    if "display_name" in fields:
        cleaned = (display_name or "").strip()
        user.display_name = cleaned or None
    await db.commit()
    await db.refresh(user)
    return user
