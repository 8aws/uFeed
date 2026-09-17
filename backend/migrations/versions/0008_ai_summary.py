"""ai summary on articles

Revision ID: 0008_ai_summary
Revises: 0007_embeddings
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_ai_summary"
down_revision: str | None = "0007_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("ai_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("articles", "ai_summary")
