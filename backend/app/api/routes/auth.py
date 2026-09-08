from __future__ import annotations

from fastapi import APIRouter

from app.api.errors import not_implemented
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    Tokens,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest) -> AuthResponse:
    raise not_implemented("auth.register")


@router.post("/login", response_model=Tokens)
async def login(body: LoginRequest) -> Tokens:
    raise not_implemented("auth.login")


@router.post("/refresh", response_model=Tokens)
async def refresh(body: RefreshRequest) -> Tokens:
    raise not_implemented("auth.refresh")
