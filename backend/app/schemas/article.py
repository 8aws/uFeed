from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    url: str | None = None
    title: str | None = None
    author: str | None = None
    summary: str | None = None
    content_html: str | None = None
    lang: str | None = None
    word_count: int | None = None
    tags: list[str] = []
    published_at: datetime | None = None
    is_read: bool = False
    is_saved: bool = False
    is_favorite: bool = False


class MarkAllReadRequest(BaseModel):
    folder_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None


class ReadEventRequest(BaseModel):
    dwell_ms: int = 0
    completion: float = 0.0


class TrendingItem(BaseModel):
    article: ArticleOut
    readers: int
    avg_completion: float
    avg_dwell_ms: int
    score: float
