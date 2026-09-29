"""resource monitor: periodic samples and daily usage

Revision ID: 0021_metrics
Revises: 0020_decode_titles
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_metrics"
down_revision: str | None = "0020_decode_titles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_samples",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
    )
    op.create_index("ix_metric_samples_ts", "metric_samples", ["ts"])
    op.create_table(
        "usage_daily",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("usage_daily")
    op.drop_index("ix_metric_samples_ts", table_name="metric_samples")
    op.drop_table("metric_samples")
