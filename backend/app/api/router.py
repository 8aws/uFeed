from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    articles,
    auth,
    folders,
    foryou,
    insights,
    keys,
    me,
    public,
    sources,
    trending,
)

# Internal API, mounted under /api by app.main.
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(me.router)
api_router.include_router(keys.router)
api_router.include_router(folders.router)
api_router.include_router(sources.router)
api_router.include_router(articles.router)
api_router.include_router(trending.router)
api_router.include_router(insights.router)
api_router.include_router(foryou.router)

# Public API (/api/v1/...)
api_router.include_router(public.router)
