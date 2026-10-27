"""Enrolment and checking of the one-time codes of editors and admins."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import totp
from app.models.recovery_code import RecoveryCode
from app.models.user import User


def is_staff(user: User) -> bool:
    return user.role in ("editor", "admin")


async def recovery_left(db: AsyncSession, user: User) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(RecoveryCode)
            .where(RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None))
        )
    ) or 0


async def begin_setup(db: AsyncSession, user: User) -> tuple[str, str]:
    """A fresh secret, pending until `enable` gets the first code. Starting
    again before that just replaces the pending secret."""
    secret = totp.generate_secret()
    user.totp_secret = totp.seal(secret)
    user.totp_enabled_at = None
    user.totp_last_step = None
    await db.commit()
    return secret, totp.otpauth_url(secret, user.email)


async def _new_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    codes = totp.new_recovery_codes()
    await db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    db.add_all([RecoveryCode(user_id=user.id, code_hash=totp.hash_recovery(c)) for c in codes])
    await db.commit()
    return codes


def _secret(user: User) -> str | None:
    return totp.unseal(user.totp_secret) if user.totp_secret else None


async def enable(db: AsyncSession, user: User, code: str) -> list[str] | None:
    """The first valid code turns it on and returns the recovery codes (shown
    once). None when the code is wrong or there is nothing pending."""
    secret = _secret(user)
    if secret is None or user.totp_enabled_at is not None:
        return None
    step = totp.check_code(secret, code, None)
    if step is None:
        return None
    user.totp_enabled_at = datetime.now(UTC)
    user.totp_last_step = step
    return await _new_recovery_codes(db, user)


async def verify(db: AsyncSession, user: User, code: str) -> bool:
    """A current code, or an unused recovery code (which is then spent)."""
    if not user.totp_enabled:
        return False
    if totp.looks_like_recovery(code):
        spent = await db.execute(
            update(RecoveryCode)
            .where(
                RecoveryCode.user_id == user.id,
                RecoveryCode.code_hash == totp.hash_recovery(code),
                RecoveryCode.used_at.is_(None),
            )
            .values(used_at=datetime.now(UTC))
        )
        await db.commit()
        return spent.rowcount == 1
    secret = _secret(user)
    if secret is None:
        return False
    step = totp.check_code(secret, code, user.totp_last_step)
    if step is None:
        return False
    # Compare-and-set so two requests with the same code can't both pass.
    claimed = await db.execute(
        update(User)
        .where(
            User.id == user.id,
            (User.totp_last_step.is_(None)) | (User.totp_last_step < step),
        )
        .values(totp_last_step=step)
    )
    await db.commit()
    return claimed.rowcount == 1


async def new_recovery_codes(db: AsyncSession, user: User) -> list[str]:
    return await _new_recovery_codes(db, user)


async def disable(db: AsyncSession, user: User) -> None:
    """Also the server-side rescue: the next admin/editor request asks to enrol again."""
    user.totp_secret = None
    user.totp_enabled_at = None
    user.totp_last_step = None
    await db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    await db.commit()
