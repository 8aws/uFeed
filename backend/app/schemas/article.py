from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AISummaryOut(BaseModel):
    """LLM summary of an article in one language (null until generated)."""

    lang: str
    summary: str | None = None
    title: str | None = None  # translated headline, when the article is in another language
    model: str | None = None
    cached: bool = False
    # ready | queued | running | failed | none (not asked for yet)
    status: str = "none"
    position: int | None = None  # in the AI queue, while queued
    eta_s: int | None = None  # estimated seconds until ready
    error: str | None = None


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    url: str | None = None
    title: str | None = None
    author: str | None = None
    summary: str | None = None
    ai_summary: str | None = None
    content_html: str | None = None
    image_url: str | None = None
    lang: str | None = None
    word_count: int | None = None
    tags: list[str] = []
    published_at: datetime | None = None
    fetched_at: datetime | None = None  # when uFeed got it (offline "mark all" cutoff)
    full_status: str | None = None  # "ok" when the full article text is available
    is_read: bool = False
    is_saved: bool = False
    is_favorite: bool = False
    dup_count: int = 1  # copies in the user's own feeds (1 = just this one)
    other_copies: int = 0  # copies in feeds the user doesn't follow (a hint only)


class TwinOut(BaseModel):
    """Another copy of the same story. `article_id` is set only when it is in a
    feed the user follows; otherwise just enough to read it on its site or to
    follow that feed."""

    article_id: uuid.UUID | None = None
    title: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    source_title: str | None = None
    site_url: str | None = None
    followed: bool = False
    is_read: bool = False


class UnreadCountsOut(BaseModel):
    """What the badges show: the user's own unread, one per duplicate story."""

    total: int = 0
    folders: dict[uuid.UUID, int] = {}


class TranslationOut(BaseModel):
    """An article machine-translated into `lang` (null until generated)."""

    lang: str
    source_lang: str
    title: str | None = None
    paragraphs: list[str] | None = None
    cached: bool = False


class FullTextOut(BaseModel):
    """The article's full text (from its web page), when the feed had only an excerpt."""

    html: str | None = None
    words: int = 0
    status: str | None = None  # "ok" | "failed"


class ArticleAudioOut(BaseModel):
    url: str  # signed, short-lived
    lang: str
    cached: bool


class MarkAllReadRequest(BaseModel):
    folder_id: uuid.UUID | None = None
    source_id: uuid.UUID | None = None
    # Only articles fetched up to this moment (when the user pressed the button,
    # possibly offline): later arrivals stay unread.
    before: datetime | None = None


class ReadEventRequest(BaseModel):
    dwell_ms: int = 0
    completion: float = 0.0
    # When it happened (events recorded offline are sent later).
    at: datetime | None = None


class TrendingItem(BaseModel):
    article: ArticleOut
    readers: int
    avg_completion: float
    avg_dwell_ms: int
    score: float


class EngageRequest(BaseModel):
    kind: str  # "open" | "share" | "skip"
    at: datetime | None = None  # when it happened (offline events arrive late)


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
