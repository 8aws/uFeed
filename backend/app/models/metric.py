from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MetricSample(Base):
    """A snapshot of the instance's load (taken by the worker every 15 min):
    host load/memory, AI service memory, storage and users."""

    __tablename__ = "metric_samples"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    data: Mapped[dict] = mapped_column(JSON, nullable=False)


class UsageDaily(Base):
    """Heavy work done per day (voices, translations, AI summaries: count and
    total time), rolled up from counters kept in Redis during the day."""

    __tablename__ = "usage_daily"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
