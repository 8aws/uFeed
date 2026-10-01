from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.api.errors import AppError
from app.core.config import settings
from app.core.ratelimit import check_rate
from app.core.security import verify_password
from app.models.user import User
from app.schemas.auth import Tokens
from app.schemas.common import OkResponse
from app.schemas.user import AccountDelete, PasswordChange, UserOut, UserUpdate
from app.services import auth as auth_service
from app.services import moderation

router = APIRouter(tags=["me"])
log = logging.getLogger("ufeed.diag")


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
    if settings.is_protected(user.email):
        raise AppError(403, "demo_account", "The demo account can't change its password.")
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
    if settings.is_protected(user.email):
        raise AppError(403, "demo_account", "The demo account can't be deleted.")
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


class DiagReport(BaseModel):
    """What the app saw before it stopped answering taps (temporary
    diagnostics): heartbeats, taps that never became a click, stalls."""

    events: list[dict[str, Any]] = Field(default_factory=list, max_length=120)
    context: dict[str, Any] = Field(default_factory=dict)


@router.post("/me/diag", response_model=OkResponse)
async def client_diag(body: DiagReport, user: CurrentUser) -> OkResponse:
    """Store a client diagnostics report in the server log."""
    if await check_rate(f"diag:{user.id}", 20, window_s=3600):
        payload = json.dumps(body.model_dump(), ensure_ascii=False, default=str)[:20000]
        log.warning("client diag user=%s %s", user.id, payload)
    return OkResponse()
