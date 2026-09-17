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
    image_url: str | None = None
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


class EngageRequest(BaseModel):
    kind: str  # "open" | "share" | "skip"


class RankedArticle(BaseModel):
    article: ArticleOut
    readers: int
    quality: float  # 0..1, blends completion and length-normalised dwell
    saves: int
    favorites: int
    opens: int
    score: float


class Insights(BaseModel):
    trending_now: list[RankedArticle]  # recency-decayed velocity
    top: list[RankedArticle]  # most readers in the window
    most_saved: list[RankedArticle]  # saves + favorites
    deep_reads: list[RankedArticle]  # highest reading quality
    hidden_gems: list[RankedArticle]  # high quality, few readers
