from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.roles import Role


class SiteConfig(BaseModel):
    """Public, unauthenticated instance info for the login screen."""

    registration_open: bool
    refresh_cooldown_s: dict[str, int]


class AdminSettings(BaseModel):
    registration_open: bool
    default_role: Role
    roles: list[str]
    refresh_cooldown_s: dict[str, int]


class AdminSettingsUpdate(BaseModel):
    registration_open: bool | None = None
    default_role: Role | None = None


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime
    feeds: int = 0


class AdminUserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None
