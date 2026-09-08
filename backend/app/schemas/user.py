from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

Locale = Literal["en", "es"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    locale: Locale
    is_active: bool
    created_at: datetime


class UserUpdate(BaseModel):
    locale: Locale | None = None
