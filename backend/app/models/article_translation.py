from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArticleTranslation(Base):
    """Machine translation of an article into a reader's language (generated on
    demand, shared by every reader of that language). The body is kept as a
    list of plain-text paragraphs, which is all the reader and the voice need."""

    __tablename__ = "article_translations"

    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    lang: Mapped[str] = mapped_column(String(5), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    paragraphs: Mapped[list] = mapped_column(JSON, nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
