from __future__ import annotations

import uuid
from datetime import datetime
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feed_url: str
    site_url: str | None = None
    title: str | None = None
    favicon_url: str | None = None
    error_count: int = 0


class SourceHealthOut(BaseModel):
    source_id: uuid.UUID
    subscription_id: uuid.UUID | None = None
    title: str | None = None
    feed_url: str
    site_url: str | None = None
    status: str
    error_count: int = 0
    last_error: str | None = None
    last_error_at: datetime | None = None
    last_fetch_at: datetime | None = None
    last_article_at: datetime | None = None
    subscribers: int = 0


class SourcePauseRequest(BaseModel):
    paused: bool


class SubscribeRequest(BaseModel):
    url: str = Field(max_length=2048)
    folder_id: uuid.UUID | None = None

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str) -> str:
        parts = urlsplit(v.strip())
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("must be an http(s) URL")
        return v.strip()


class SubscriptionUpdate(BaseModel):
    folder_id: uuid.UUID | None = None
    custom_title: str | None = None
    muted: bool | None = None


class MutedKeywordIn(BaseModel):
    keyword: str = Field(min_length=1, max_length=100)


class MutedKeywordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    keyword: str


class RefreshResult(BaseModel):
    checked: int
    new_articles: int
    errors: int


class SyncResult(RefreshResult):
    """Opportunistic refresh on app open; skipped=True when nothing was due or
    the per-user sync cooldown applies."""

    skipped: bool = False


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: SourceOut
    folder_id: uuid.UUID | None = None
    custom_title: str | None = None
    unread_count: int = 0
    muted: bool = False
