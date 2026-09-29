"""full article text for feeds that only publish an excerpt

Revision ID: 0022_full_text
Revises: 0021_metrics
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_full_text"
down_revision: str | None = "0021_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("full_html", sa.Text()))
    op.add_column("articles", sa.Column("full_status", sa.String(16)))
    op.add_column("articles", sa.Column("full_fetched_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("articles", "full_fetched_at")
    op.drop_column("articles", "full_status")
    op.drop_column("articles", "full_html")
