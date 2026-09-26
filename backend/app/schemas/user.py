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


class UserUpdate(BaseModel):
    locale: Locale | None = None
    display_name: str | None = Field(default=None, max_length=60)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=256)
