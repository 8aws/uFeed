from __future__ import annotations

from fastapi import Header

from app.core.i18n import resolve_locale

# NOTE: authentication dependencies (JWT / API key) are implemented in WS1.
# This module currently exposes only request-scoped helpers that other
# workstreams can build on without changing the contract.


async def request_locale(accept_language: str | None = Header(default=None)) -> str:
    """Resolve the effective locale for the request."""
    return resolve_locale(accept_language)
