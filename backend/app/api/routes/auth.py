from __future__ import annotations

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends

from app.api.deps import DbSession, rate_limit_auth
from app.api.errors import AppError
from app.core.config import settings
from app.core.ratelimit import check_rate
from app.core.security import (
    create_reset_token,
    decode_token,
    token_version_ok,
    user_id_from_sub,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ForgotRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetRequest,
    Tokens,
)
from app.schemas.common import OkResponse
from app.services import auth as auth_service
from app.services import mailer, moderation
from app.services import site as site_service

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(rate_limit_auth)])


def _tokens_for(user: User) -> Tokens:
    return auth_service.tokens_for(user)


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest, db: DbSession) -> AuthResponse:
    if await auth_service.get_user_by_email(db, body.email):
        raise AppError(409, "email_taken", "That email is already registered.")
    # The first account of an empty instance can always register and becomes
    # the admin; after that, admins can close sign-ups and pick the default plan.
    if await moderation.active_ban(db, body.email):
        raise AppError(403, "registration_banned", "This email can't register an account.")
    cfg = await site_service.get_settings(db)
    first = await site_service.user_count(db) == 0
    if not first and not cfg["registration_open"]:
        raise AppError(403, "registration_closed", "Registration is currently closed.")
    locale = body.locale or settings.default_locale
    role = "admin" if first else cfg["default_role"]
    user = await auth_service.create_user(db, body.email, body.password, locale, role)
    return AuthResponse(user=user, tokens=_tokens_for(user))


@router.post("/login", response_model=Tokens)
async def login(body: LoginRequest, db: DbSession) -> Tokens:
    user = await auth_service.get_user_by_email(db, body.email)
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Invalid email or password.")
    # Only reveal the account's status to someone who knows the password.
    if not user.is_active:
        raise AppError(403, "account_disabled", "This account is disabled.")
    if moderation.is_suspended(user):
        until = user.suspended_until.isoformat() if user.suspended_until else ""
        raise AppError(403, "account_suspended", f"This account is suspended until {until}.")
    if moderation.is_dormant(user):
        await moderation.reactivate(db, user)  # signing in reclaims the account
    await moderation.touch(db, user)
    return _tokens_for(user)


@router.post("/refresh", response_model=Tokens)
async def refresh(body: RefreshRequest, db: DbSession) -> Tokens:
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError as exc:
        raise AppError(401, "invalid_token", "Invalid or expired refresh token.") from exc
    if payload.get("type") != "refresh":
        raise AppError(401, "invalid_token", "Not a refresh token.")
    user_id = user_id_from_sub(payload.get("sub", ""))
    user = await db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise AppError(401, "invalid_token", "User not found or inactive.")
    if not token_version_ok(payload, user.token_version) or moderation.is_suspended(user):
        raise AppError(401, "invalid_token", "Session expired; please sign in again.")
    return _tokens_for(user)


RESET_MAIL = {
    "es": (
        "Restablece tu contraseña de uFeed",
        "Hola:\n\nAlguien (seguramente tú) ha pedido restablecer la contraseña de tu "
        "cuenta de uFeed. Para elegir una nueva, abre este enlace en la próxima hora:\n\n"
        "{link}\n\nSi no lo has pedido tú, ignora este correo: tu contraseña no cambia.\n\n"
        "uFeed",
    ),
    "en": (
        "Reset your uFeed password",
        "Hi,\n\nSomeone (probably you) asked to reset the password of your uFeed "
        "account. To choose a new one, open this link within the next hour:\n\n{link}\n\n"
        "If it wasn't you, ignore this email: your password stays the same.\n\nuFeed",
    ),
}


async def _send_reset(email: str, user_id: str, version: int, locale: str) -> None:
    token = create_reset_token(user_id, version)
    link = f"{settings.public_url.rstrip('/')}/reset?token={token}"
    subject, body = RESET_MAIL.get((locale or "en")[:2], RESET_MAIL["en"])
    await mailer.send(email, subject, body.format(link=link))


@router.post("/forgot", response_model=OkResponse)
async def forgot_password(
    body: ForgotRequest, db: DbSession, background: BackgroundTasks
) -> OkResponse:
    """Email a one-time link to choose a new password. Always answers the same,
    so it doesn't reveal which addresses have an account."""
    email = body.email.lower()
    user = await auth_service.get_user_by_email(db, email)
    allowed = await check_rate(f"forgot:{email}", 3, window_s=3600)
    if (
        user is not None
        and allowed
        and user.is_active
        and not moderation.is_suspended(user)
        and not settings.is_protected(user.email)
    ):
        # Sent after replying: the answer takes as long either way.
        background.add_task(_send_reset, user.email, str(user.id), user.token_version, user.locale)
    return OkResponse()


@router.post("/reset", response_model=Tokens)
async def reset_password(body: ResetRequest, db: DbSession) -> Tokens:
    """Set a new password from an emailed link (once); signs out every other
    session and signs this one in."""
    try:
        payload = decode_token(body.token)
    except jwt.PyJWTError as exc:
        raise AppError(400, "invalid_reset", "This link has expired or is not valid.") from exc
    user_id = user_id_from_sub(payload.get("sub", "")) if payload.get("type") == "reset" else None
    user = await db.get(User, user_id) if user_id else None
    if (
        user is None
        or not user.is_active
        or not token_version_ok(payload, user.token_version)
        or settings.is_protected(user.email)
    ):
        raise AppError(400, "invalid_reset", "This link has expired or is not valid.")
    user = await auth_service.set_password(db, user, body.new_password)
    await moderation.touch(db, user)
    return _tokens_for(user)
