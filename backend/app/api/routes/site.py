from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession
from app.core.roles import REFRESH_COOLDOWN_S
from app.schemas.admin import SiteConfig
from app.services import site as site_service

router = APIRouter(tags=["site"])


@router.get("/site", response_model=SiteConfig)
async def site_config(db: DbSession) -> SiteConfig:
    """Unauthenticated instance info (e.g. whether sign-ups are open)."""
    cfg = await site_service.get_settings(db)
    open_ = cfg["registration_open"] or await site_service.user_count(db) == 0
    return SiteConfig(registration_open=open_, refresh_cooldown_s=dict(REFRESH_COOLDOWN_S))
