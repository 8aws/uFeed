"""daily digest: which days of the week (bit per day, Monday = 1)

Revision ID: 0024_digest_days
Revises: 0023_daily_digest
Create Date: 2026-10-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_digest_days"
down_revision: str | None = "0023_daily_digest"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("digest_days", sa.SmallInteger(), nullable=False, server_default="127"),
    )


def downgrade() -> None:
    op.drop_column("users", "digest_days")
