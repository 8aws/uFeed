from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from app.schemas.article import ArticleOut


class CatalogFeed(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    url: str = Field(max_length=2048)
    lang: Literal["en", "es"]

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str) -> str:
        parts = urlsplit(v.strip())
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("must be an http(s) URL")
        return v.strip()


class CatalogSection(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name_en: str = Field(min_length=1, max_length=80)
    name_es: str = Field(min_length=1, max_length=80)
    feeds: list[CatalogFeed] = Field(max_length=30)


class Catalog(BaseModel):
    """The starter suggestions new accounts see. `sections` is None while the
    instance uses the built-in list shipped with the app."""

    sections: list[CatalogSection] | None = Field(default=None, max_length=40)
    updated_at: datetime | None = None

    @field_validator("sections")
    @classmethod
    def _unique_ids(cls, v: list[CatalogSection] | None) -> list[CatalogSection] | None:
        if v is not None and len({s.id for s in v}) != len(v):
            raise ValueError("section ids must be unique")
        return v


class HiddenArticleOut(BaseModel):
    article: ArticleOut
    hidden_at: datetime
    hidden_by: str | None = None


class HideRequest(BaseModel):
    hidden: bool


class HiddenIds(BaseModel):
    ids: list[uuid.UUID]
