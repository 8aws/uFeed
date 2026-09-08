from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feed_url: str
    site_url: str | None = None
    title: str | None = None
    favicon_url: str | None = None


class SubscribeRequest(BaseModel):
    url: str
    folder_id: uuid.UUID | None = None


class SubscriptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: SourceOut
    folder_id: uuid.UUID | None = None
    custom_title: str | None = None
    unread_count: int = 0
