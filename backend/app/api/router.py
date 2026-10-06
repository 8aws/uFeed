from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    admin,
    articles,
    audio,
    auth,
    curation,
    digest,
    filters,
    folders,
    foryou,
    insights,
    keys,
    me,
    public,
    site,
    sources,
    trending,
)

# Internal API, mounted under /api by app.main.
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(keys.router)
api_router.include_router(folders.router)
api_router.include_router(filters.router)
api_router.include_router(sources.router)
api_router.include_router(articles.router)
api_router.include_router(audio.router)
api_router.include_router(trending.router)
api_router.include_router(insights.router)
api_router.include_router(foryou.router)
api_router.include_router(site.router)
api_router.include_router(admin.router)
api_router.include_router(curation.router)
api_router.include_router(digest.router)

# Public API (/api/v1/...)
api_router.include_router(public.router)
