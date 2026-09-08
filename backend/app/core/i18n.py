from __future__ import annotations

from app.core.config import settings


def resolve_locale(accept_language: str | None) -> str:
    """Resolve a supported locale from an Accept-Language header.

    Falls back to the configured default. Very small parser: enough for
    EN/ES negotiation; a fuller implementation can arrive with the API work.
    """
    if not accept_language:
        return settings.default_locale
    for part in accept_language.split(","):
        code = part.split(";")[0].strip().lower()
        base = code.split("-")[0]
        if base in settings.supported_locales:
            return base
    return settings.default_locale
