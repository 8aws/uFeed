from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    locale: Mapped[str] = mapped_column(String(5), default="en", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Plan/role: free | general | vip | editor | admin (see app.core.roles).
    role: Mapped[str] = mapped_column(String(16), default="free", nullable=False)
    # Bumped on password change/reset or deactivation; tokens carry it ("tv")
    # so older sessions stop working.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Created by "continue without an account": no real email or password, the
    # device holds the only session. Upgrading to a real account keeps the data.
    is_guest: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Temporary suspension/ban: no access until this moment (lifts by itself).
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Last authenticated web activity (updated at most hourly); with API-key
    # use it drives the inactivity clean-up.
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Deactivated for inactivity at this moment (stage 1). Signing in again or
    # using an API key reclaims it; otherwise it's deleted later (stage 2).
    dormant_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Daily digest email: local hour to send it (settings.digest_tz), None = off;
    # and the last day it went out (one a day).
    digest_hour: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    digest_sent_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Days it goes out: a bit per weekday, Monday = 1 ... Sunday = 64 (127 = all,
    # 31 = Monday to Friday, 96 = weekend).
    digest_days: Mapped[int] = mapped_column(
        SmallInteger, default=127, server_default="127", nullable=False
    )
    # One-time codes for editors and admins (see app.core.totp). The secret is
    # sealed; it is "pending" until the first code proves the device has it.
    totp_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Last time step accepted: a code works once.
    totp_last_step: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    @property
    def totp_enabled(self) -> bool:
        return self.totp_secret is not None and self.totp_enabled_at is not None
