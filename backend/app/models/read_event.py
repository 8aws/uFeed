from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReadEvent(Base):
    """One anonymised reading event, used for cross-user trending.

    Rows carry user_id (to count distinct readers and cap self-inflation) but
    are only ever exposed in aggregate — never per user.
    """

    __tablename__ = "read_events"
    __table_args__ = (
        Index("ix_read_events_article", "article_id"),
        Index("ix_read_events_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    article_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    dwell_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
