from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, StaffUser, rate_limit_auth
from app.api.errors import AppError
from app.core.config import settings
from app.core.ratelimit import check_rate
from app.core.security import create_step_up_token, verify_password
from app.models.user import User
from app.schemas.common import OkResponse
from app.schemas.staff_totp import (
    RecoveryCodes,
    StepUp,
    TotpCode,
    TotpDisable,
    TotpEnabled,
    TotpSetup,
    TotpStatus,
)
from app.services import staff_totp

router = APIRouter(prefix="/staff/totp", tags=["staff"], dependencies=[Depends(rate_limit_auth)])


async def _throttle(user: User) -> None:
    """Six digits can be guessed, so wrong tries are scarce: a few every few
    minutes and a hard cap per hour, per account."""
    if not await check_rate(f"totp:{user.id}", 5, window_s=300) or not await check_rate(
        f"totp-h:{user.id}", 20, window_s=3600
    ):
        raise AppError(429, "rate_limited", "Too many attempts; try again in a few minutes.")


def _step_up(user: User) -> StepUp:
    return StepUp(
        step_up_token=create_step_up_token(str(user.id), user.token_version),
        expires_in=settings.staff_session_hours * 3600,
    )


async def _checked(db: DbSession, user: User, code: str) -> None:
    await _throttle(user)
    if not await staff_totp.verify(db, user, code):
        raise AppError(403, "invalid_code", "That code is not valid.")


@router.get("", response_model=TotpStatus)
async def status(user: StaffUser, db: DbSession) -> TotpStatus:
    return TotpStatus(
        enabled=user.totp_enabled,
        pending=user.totp_secret is not None and not user.totp_enabled,
        required=settings.staff_totp,
        recovery_left=await staff_totp.recovery_left(db, user),
    )


@router.post("/setup", response_model=TotpSetup)
async def setup(user: StaffUser, db: DbSession) -> TotpSetup:
    if user.totp_enabled:
        raise AppError(409, "totp_already_enabled", "One-time codes are already set up.")
    secret, url = await staff_totp.begin_setup(db, user)
    return TotpSetup(secret=secret, otpauth_url=url)


@router.post("/enable", response_model=TotpEnabled)
async def enable(body: TotpCode, user: StaffUser, db: DbSession) -> TotpEnabled:
    await _throttle(user)
    codes = await staff_totp.enable(db, user, body.code)
    if codes is None:
        raise AppError(403, "invalid_code", "That code is not valid.")
    return TotpEnabled(**_step_up(user).model_dump(), recovery_codes=codes)


@router.post("/verify", response_model=StepUp)
async def verify(body: TotpCode, user: StaffUser, db: DbSession) -> StepUp:
    await _checked(db, user, body.code)
    return _step_up(user)


@router.post("/recovery-codes", response_model=RecoveryCodes)
async def recovery_codes(body: TotpCode, user: StaffUser, db: DbSession) -> RecoveryCodes:
    """Ten new codes (the old ones stop working); asks for a code to confirm."""
    await _checked(db, user, body.code)
    return RecoveryCodes(recovery_codes=await staff_totp.new_recovery_codes(db, user))


@router.post("/disable", response_model=OkResponse)
async def disable(body: TotpDisable, user: StaffUser, db: DbSession) -> OkResponse:
    """Turn it off (to enrol a new phone): needs a code and the password."""
    await _throttle(user)
    if not verify_password(body.password, user.password_hash):
        raise AppError(403, "invalid_credentials", "Wrong password.")
    if not await staff_totp.verify(db, user, body.code):
        raise AppError(403, "invalid_code", "That code is not valid.")
    await staff_totp.disable(db, user)
    return OkResponse()
