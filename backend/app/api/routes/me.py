from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.api.errors import AppError
from app.core.ratelimit import check_rate
from app.core.security import verify_password
from app.models.user import User
from app.schemas.auth import Tokens
from app.schemas.common import OkResponse
from app.schemas.user import AccountDelete, PasswordChange, UserOut, UserUpdate
from app.services import auth as auth_service
from app.services import moderation

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


@router.post("/me/delete", response_model=OkResponse)
async def delete_account(body: AccountDelete, user: CurrentUser, db: DbSession) -> OkResponse:
    """Delete your own account and all its data (feeds, folders, saved and
    read state, API keys). Asks for the password; the last administrator
    can't delete themselves (the instance would be left without one)."""
    if not await check_rate(f"delacct:{user.id}", 5):
        raise AppError(429, "rate_limited", "Too many attempts; try again shortly.")
    if not verify_password(body.password, user.password_hash):
        raise AppError(400, "wrong_password", "Password is incorrect.")
    if user.role == "admin":
        admins = await db.scalar(select(func.count()).select_from(User).where(User.role == "admin"))
        if (admins or 0) <= 1:
            raise AppError(
                400, "last_admin", "Make someone else admin before deleting this account."
            )
    await moderation.delete_user(db, user)
    return OkResponse()
