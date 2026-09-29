"""User roles (plans) and the default limits attached to each.

Ordered from least to most privileged. `admin` can manage the instance
(registration, roles); `editor` is reserved for curating shared content later.
Admins can override any limit from the panel (stored in app_settings); these
are the defaults.
"""

from __future__ import annotations

from typing import Any, Literal

Role = Literal["free", "general", "vip", "editor", "admin"]
ROLES: tuple[Role, ...] = ("free", "general", "vip", "editor", "admin")

# refresh_cooldown_s: seconds between manual refreshes (0 = immediate)
# max_feeds / max_api_keys: None = unlimited
# ai_features: semantic search, "For you" and similar articles
# tts_server: "listen" with the server's neural voice (the device voice is for all)
# post_radio: "Post radio" (read posts one after another); radio_max_posts /
#   radio_max_minutes cap how much one session can chain (None = unlimited)
DEFAULT_PLAN_LIMITS: dict[str, dict[str, Any]] = {
    "free": {
        "refresh_cooldown_s": 600,
        "max_feeds": 100,
        "max_api_keys": 1,
        "ai_features": True,
        "tts_server": False,
        "post_radio": False,
        "radio_max_posts": 10,
        "radio_max_minutes": 30,
    },
    "general": {
        "refresh_cooldown_s": 300,
        "max_feeds": 300,
        "max_api_keys": 3,
        "ai_features": True,
        "tts_server": True,
        "post_radio": False,
        "radio_max_posts": 10,
        "radio_max_minutes": 30,
    },
    "vip": {
        "refresh_cooldown_s": 0,
        "max_feeds": None,
        "max_api_keys": 10,
        "ai_features": True,
        "tts_server": True,
        "post_radio": True,
        "radio_max_posts": 20,
        "radio_max_minutes": 60,
    },
    "editor": {
        "refresh_cooldown_s": 0,
        "max_feeds": None,
        "max_api_keys": 10,
        "ai_features": True,
        "tts_server": True,
        "post_radio": True,
        "radio_max_posts": 20,
        "radio_max_minutes": 60,
    },
    "admin": {
        "refresh_cooldown_s": 0,
        "max_feeds": None,
        "max_api_keys": None,
        "ai_features": True,
        "tts_server": True,
        "post_radio": True,
        "radio_max_posts": None,
        "radio_max_minutes": None,
    },
}

DEFAULT_SIGNUP_ROLE: Role = "free"
