from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditEntry(Base):
    """Who did what to whom, and when, in the administration and curation.
    Emails are copied in: the entry must still read well after an account is gone."""

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_email: Mapped[str] = mapped_column(String(320), nullable=False)
    action: Mapped[str] = mapped_column(String(40), index=True, nullable=False)  # "user.delete"
    target_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    target_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
