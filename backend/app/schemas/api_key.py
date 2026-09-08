from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=list)


class ApiKeyOut(BaseModel):
    """API key metadata (never includes the secret)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    last_used_at: datetime | None = None
    created_at: datetime
    revoked_at: datetime | None = None


class ApiKeyCreated(ApiKeyOut):
    """Returned only once, at creation time, with the plaintext key."""

    key: str
