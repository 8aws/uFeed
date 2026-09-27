from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.roles import Role


class SiteConfig(BaseModel):
    """Public, unauthenticated instance info for the login screen."""

    registration_open: bool
    refresh_cooldown_s: dict[str, int]


class AdminSettings(BaseModel):
    registration_open: bool
    default_role: Role
    retention_days: int
    inactivity_days: int
    dormant_delete_days: int
    roles: list[str]
    refresh_cooldown_s: dict[str, int]


class AdminSettingsUpdate(BaseModel):
    registration_open: bool | None = None
    default_role: Role | None = None
    retention_days: int | None = Field(default=None, ge=0, le=3650)
    inactivity_days: int | None = Field(default=None, ge=0, le=3650)
    dormant_delete_days: int | None = Field(default=None, ge=0, le=3650)


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime
    feeds: int = 0
    suspended_until: datetime | None = None
    dormant_since: datetime | None = None
    last_activity_at: datetime | None = None
    banned: bool = False
    ban_until: datetime | None = None


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
    inactivity_days: int = 0
    dormant_delete_days: int = 0
    last_inactive_cleanup: dict[str, Any] | None = None
    db_size_bytes: int
    articles: int
    backups: dict[str, Any] | None = None


class SuspendRequest(BaseModel):
    days: int = Field(ge=1, le=3650)


class BanRequest(BaseModel):
    """days=None bans permanently."""

    days: int | None = Field(default=None, ge=1, le=3650)
    reason: str | None = Field(default=None, max_length=300)


class BanCreate(BanRequest):
    email: EmailStr


class BanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    until: datetime | None = None
    reason: str | None = None
    created_at: datetime
