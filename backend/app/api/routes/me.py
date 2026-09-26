from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.errors import AppError
from app.core.ratelimit import check_rate
from app.core.security import verify_password
from app.schemas.auth import Tokens
from app.schemas.user import PasswordChange, UserOut, UserUpdate
from app.services import auth as auth_service

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUser) -> UserOut:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(body: UserUpdate, user: CurrentUser, db: DbSession) -> UserOut:
    user = await auth_service.update_profile(
        db,
        user,
        fields=set(body.model_fields_set),
        locale=body.locale,
        display_name=body.display_name,
    )
    return user


@router.post("/me/password", response_model=Tokens)
async def change_password(body: PasswordChange, user: CurrentUser, db: DbSession) -> Tokens:
    """Change your password. Other sessions are signed out; this one gets new tokens."""
    if not await check_rate(f"pwd:{user.id}", 10):
        raise AppError(429, "rate_limited", "Too many attempts; try again shortly.")
    if not verify_password(body.current_password, user.password_hash):
        raise AppError(400, "wrong_password", "Current password is incorrect.")
    user = await auth_service.set_password(db, user, body.new_password)
    return auth_service.tokens_for(user)
