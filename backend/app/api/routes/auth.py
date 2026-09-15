from __future__ import annotations

import jwt
from fastapi import APIRouter

from app.api.deps import DbSession
from app.api.errors import AppError
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    user_id_from_sub,
)
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    Tokens,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens_for(user: User) -> Tokens:
    sub = str(user.id)
    return Tokens(
        access_token=create_access_token(sub),
        refresh_token=create_refresh_token(sub),
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(body: RegisterRequest, db: DbSession) -> AuthResponse:
    if await auth_service.get_user_by_email(db, body.email):
        raise AppError(409, "email_taken", "That email is already registered.")
    locale = body.locale or settings.default_locale
    user = await auth_service.create_user(db, body.email, body.password, locale)
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
    return _tokens_for(user)
