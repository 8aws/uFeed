from __future__ import annotations

from pydantic import BaseModel, Field


class DiscoverRequest(BaseModel):
    url: str = Field(max_length=2048)


class DiscoveredFeed(BaseModel):
    feed_url: str
    title: str | None = None


class OpmlImportResult(BaseModel):
    imported: int
    skipped: int
