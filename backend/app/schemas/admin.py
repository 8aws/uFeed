from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.roles import Role


class SiteConfig(BaseModel):
    """Public, unauthenticated instance info for the login screen."""

    registration_open: bool
    refresh_cooldown_s: dict[str, int]


class AdminSettings(BaseModel):
    registration_open: bool
    default_role: Role
    retention_days: int
    roles: list[str]
    refresh_cooldown_s: dict[str, int]


class AdminSettingsUpdate(BaseModel):
    registration_open: bool | None = None
    default_role: Role | None = None
    retention_days: int | None = Field(default=None, ge=0, le=3650)


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


class TemporaryPassword(BaseModel):
    """Shown once to the admin; the user must change it at next sign-in."""

    temporary_password: str


class Maintenance(BaseModel):
    """Storage/retention/backup status for the admin panel."""

    retention_days: int
    last_purge: dict[str, Any] | None = None
    db_size_bytes: int
    articles: int
    backups: dict[str, Any] | None = None
