"""User roles (plans) and the limits attached to each.

Ordered from least to most privileged. `admin` can manage the instance
(registration, roles); `editor` is reserved for curating shared content later.
"""

from __future__ import annotations

from typing import Literal

Role = Literal["free", "general", "vip", "editor", "admin"]
ROLES: tuple[Role, ...] = ("free", "general", "vip", "editor", "admin")

# Minimum seconds between on-demand refreshes ("Refresh" button / POST
# /api/refresh). Background polling by the worker is unaffected.
REFRESH_COOLDOWN_S: dict[str, int] = {
    "free": 10 * 60,
    "general": 5 * 60,
    "vip": 0,
    "editor": 0,
    "admin": 0,
}

DEFAULT_SIGNUP_ROLE: Role = "free"


def refresh_cooldown(role: str) -> int:
    return REFRESH_COOLDOWN_S.get(role, REFRESH_COOLDOWN_S["free"])
