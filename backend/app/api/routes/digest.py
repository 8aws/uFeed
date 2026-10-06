from __future__ import annotations

import jwt
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.api.deps import ApiKeyRead, CurrentUser, DbSession
from app.core.security import decode_token, user_id_from_sub
from app.models.user import User
from app.schemas.user import DigestOut
from app.services import digest as digest_service

router = APIRouter(tags=["digest"])

_OFF_PAGE = (
    '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
    '<body style="font-family:system-ui,sans-serif;max-width:32rem;margin:3rem auto;'
    'padding:0 1rem;line-height:1.5"><h2>uFeed</h2><p>{msg}</p>'
    '<p><a href="/settings">Ajustes · Settings</a></p></body>'
)


@router.get("/digest", response_model=DigestOut)
async def get_digest(
    user: CurrentUser,
    db: DbSession,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=8, ge=1, le=30),
) -> DigestOut:
    """Your digest now: the most relevant unread articles of the last `hours`."""
    return DigestOut(**await digest_service.build(db, user, hours, limit))


@router.get("/v1/digest", response_model=DigestOut, tags=["public"])
async def public_digest(
    principal: ApiKeyRead,
    db: DbSession,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=8, ge=1, le=30),
) -> DigestOut:
    """The daily digest with an API key (read scope), e.g. for a daily-summary app."""
    user = await db.get(User, principal.user_id)
    return DigestOut(**await digest_service.build(db, user, hours, limit))


async def _turn_off(db, token: str) -> HTMLResponse:
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        payload = {}
    user_id = (
        user_id_from_sub(payload.get("sub", "")) if payload.get("type") == "digest_off" else None
    )
    if user_id is None:
        msg = "Este enlace no es válido o ha caducado. · This link is not valid or has expired."
        return HTMLResponse(_OFF_PAGE.format(msg=msg), status_code=400)
    await digest_service.turn_off(db, user_id)
    msg = (
        "Listo: ya no recibirás el resumen diario. Puedes volver a activarlo en Ajustes. · "
        "Done: you won't get the daily digest any more. You can turn it back on in Settings."
    )
    return HTMLResponse(_OFF_PAGE.format(msg=msg))


@router.get("/digest/off", response_class=HTMLResponse, include_in_schema=False)
async def digest_off_link(db: DbSession, token: str = "") -> HTMLResponse:
    """Unsubscribe link in each digest email (no sign-in needed)."""
    return await _turn_off(db, token)


@router.post("/digest/off", response_class=HTMLResponse, include_in_schema=False)
async def digest_off_one_click(db: DbSession, token: str = "") -> HTMLResponse:
    """One-click unsubscribe (List-Unsubscribe-Post) from mail apps."""
    return await _turn_off(db, token)
