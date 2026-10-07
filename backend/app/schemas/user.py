from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Locale = Literal["en", "es"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str | None = None
    locale: Locale
    role: str
    is_active: bool
    must_change_password: bool = False
    created_at: datetime
    digest_hour: int | None = None  # daily digest email hour; None = off
    digest_days: int = 127  # bit per weekday, Monday = 1 ... Sunday = 64


class UserUpdate(BaseModel):
    locale: Locale | None = None
    display_name: str | None = Field(default=None, max_length=60)
    digest_hour: int | None = Field(default=None, ge=0, le=23)  # None = off
    digest_days: int | None = Field(default=None, ge=1, le=127)  # bit per weekday


class AccountDelete(BaseModel):
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=256)


class DigestItem(BaseModel):
    id: str
    title: str
    source: str
    icon_url: str | None = None  # the feed's icon
    url: str | None = None
    published_at: str
    summary: str  # the AI summary in your language if there is one, else an excerpt
    ai_summary: bool = False
    readers: int = 0  # people who read it in the last two days


class DigestOut(BaseModel):
    """The most relevant unread articles of the last hours from your feeds."""

    hours: int
    total_new: int  # unread articles in the window (before picking)
    items: list[DigestItem]
