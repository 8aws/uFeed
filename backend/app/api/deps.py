from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import AppError
from app.core.config import settings
from app.core.i18n import resolve_locale
from app.core.ratelimit import check_rate
from app.core.security import decode_token, token_version_ok, user_id_from_sub
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.services.api_keys import resolve_api_key

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def request_locale(accept_language: str | None = Header(default=None)) -> str:
    """Resolve the effective locale for the request."""
    return resolve_locale(accept_language)


def _unauthorized(message: str = "Authentication required.") -> AppError:
    return AppError(status_code=401, code="unauthorized", message=message)


async def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    """Authenticate an internal request via a JWT access token."""
    if creds is None:
        raise _unauthorized()
    try:
        payload = decode_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid or expired token.") from exc
    if payload.get("type") != "access":
        raise _unauthorized("Wrong token type.")
    user_id = user_id_from_sub(payload.get("sub", ""))
    if user_id is None:
        raise _unauthorized("Invalid token subject.")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("User not found or inactive.")
    if not token_version_ok(payload, user.token_version):
        raise _unauthorized("Session expired; please sign in again.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_api_key(
    db: DbSession,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiKey:
    """Authenticate a public (/api/v1) request via an API key."""
    if not x_api_key:
        raise _unauthorized("Missing X-API-Key header.")
    key = await resolve_api_key(db, x_api_key)
    if key is None:
        raise _unauthorized("Invalid API key.")
    owner = await db.get(User, key.user_id)
    if owner is None or not owner.is_active:
        raise _unauthorized("Account disabled.")
    if not await check_rate(f"pub:{key.id}", settings.rate_limit_public_per_min):
        raise AppError(429, "rate_limited", "Rate limit exceeded for this API key.")
    return key


ApiKeyPrincipal = Annotated[ApiKey, Depends(get_api_key)]


def require_scope(scope: str):
    """API-key dependency that also checks a scope.

    Keys with no scopes are full-access for their owner (legacy/default);
    otherwise the key must list the scope. "read" covers GETs, "state" covers
    changing article state (read / saved / favourite).
    """

    async def _dep(key: ApiKeyPrincipal) -> ApiKey:
        if key.scopes and scope not in key.scopes:
            raise AppError(403, "insufficient_scope", f"This API key lacks the '{scope}' scope.")
        return key

    return _dep


ApiKeyRead = Annotated[ApiKey, Depends(require_scope("read"))]
ApiKeyState = Annotated[ApiKey, Depends(require_scope("state"))]


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise AppError(403, "forbidden", "Administrator access required.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


async def rate_limit_auth(request: Request) -> None:
    """Throttle auth endpoints per client IP to blunt brute-force attempts."""
    ip = request.client.host if request.client else "unknown"
    if not await check_rate(f"auth:{ip}", settings.rate_limit_auth_per_min):
        raise AppError(429, "rate_limited", "Too many attempts; try again shortly.")


RateLimitAuth = Annotated[None, Depends(rate_limit_auth)]
