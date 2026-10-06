"""daily digest by email: chosen hour and last day sent

Revision ID: 0023_daily_digest
Revises: 0022_full_text
Create Date: 2026-10-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_daily_digest"
down_revision: str | None = "0022_full_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("digest_hour", sa.SmallInteger()))
    op.add_column("users", sa.Column("digest_sent_on", sa.Date()))


def downgrade() -> None:
    op.drop_column("users", "digest_sent_on")
    op.drop_column("users", "digest_hour")
