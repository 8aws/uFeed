from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Page[T](BaseModel):
    """Cursor-paginated collection: {items, next_cursor}."""

    items: list[T]
    next_cursor: str | None = None


class OkResponse(BaseModel):
    ok: bool = True
