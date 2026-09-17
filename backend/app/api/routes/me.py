from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.user import UserOut, UserUpdate
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
