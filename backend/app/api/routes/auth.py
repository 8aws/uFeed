from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends

from app.api.deps import DbSession, rate_limit_auth
from app.api.errors import AppError
from app.core.config import settings
from app.core.security import decode_token, token_version_ok, user_id_from_sub
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    Tokens,
)
from app.services import auth as auth_service
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
    user = await auth_service.authenticate(db, body.email, body.password)
    if user is None:
        raise AppError(401, "invalid_credentials", "Invalid email or password.")
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
    if not token_version_ok(payload, user.token_version):
        raise AppError(401, "invalid_token", "Session expired; please sign in again.")
    return _tokens_for(user)
