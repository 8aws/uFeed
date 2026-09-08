from __future__ import annotations

from fastapi import APIRouter

from app.api.errors import not_implemented
from app.schemas.user import UserOut, UserUpdate

router = APIRouter(tags=["me"])


@router.get("/me", response_model=UserOut)
async def get_me() -> UserOut:
    raise not_implemented("me.get")


@router.patch("/me", response_model=UserOut)
async def update_me(body: UserUpdate) -> UserOut:
    raise not_implemented("me.update")
