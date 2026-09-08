from __future__ import annotations

from pydantic import BaseModel


class DiscoverRequest(BaseModel):
    url: str


class DiscoveredFeed(BaseModel):
    feed_url: str
    title: str | None = None


class OpmlImportResult(BaseModel):
    imported: int
    skipped: int
