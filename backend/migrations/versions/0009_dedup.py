"""semantic dedup group

Revision ID: 0009_dedup
Revises: 0008_ai_summary
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_dedup"
down_revision: str | None = "0008_ai_summary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Group id for near-duplicate articles; the "seed" article has id == group.
    op.add_column("articles", sa.Column("dup_group_id", sa.Uuid(), nullable=True))
    op.create_index("ix_articles_dup_group", "articles", ["dup_group_id"])


def downgrade() -> None:
    op.drop_index("ix_articles_dup_group", table_name="articles")
    op.drop_column("articles", "dup_group_id")
