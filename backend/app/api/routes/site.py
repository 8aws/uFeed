from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.api.routes.curation import load_catalog
from app.schemas.admin import SiteConfig
from app.schemas.curation import Catalog
from app.services import site as site_service

router = APIRouter(tags=["site"])


@router.get("/site", response_model=SiteConfig)
async def site_config(db: DbSession) -> SiteConfig:
    """Unauthenticated instance info (e.g. whether sign-ups are open)."""
    cfg = await site_service.get_settings(db)
    open_ = cfg["registration_open"] or await site_service.user_count(db) == 0
    plans = await site_service.plan_limits(db)
    return SiteConfig(
        registration_open=open_,
        refresh_cooldown_s={r: int(p["refresh_cooldown_s"]) for r, p in plans.items()},
        plan_limits=plans,
        contact_email=cfg.get("contact_email") or "",
    )


@router.get("/catalog", response_model=Catalog)
async def starter_catalog(_: CurrentUser, db: DbSession) -> Catalog:
    """The starter suggestions curated by editors (sections=None: the app's
    built-in list applies)."""
    return await load_catalog(db)
