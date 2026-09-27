from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_error_handlers
from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import settings


def create_app() -> FastAPI:
    # Interactive docs and the schema map every endpoint; don't publish them in
    # production (the contract lives in API/openapi.json in the repo).
    docs = settings.env != "prod"
    app = FastAPI(
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
        title="uFeed API",
        version=__version__,
        description=(
            "Self-hosted, multi-user, multilingual RSS/Atom reader. "
            "Internal API under /api, public API under /api/v1."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    # Health at root; everything else under /api.
    app.include_router(health_router)
    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
