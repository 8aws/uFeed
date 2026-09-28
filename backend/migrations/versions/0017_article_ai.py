"""on-demand LLM summaries/translations per article and language

Revision ID: 0017_article_ai
Revises: 0016_mutes
Create Date: 2026-09-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_article_ai"
down_revision: str | None = "0016_mutes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "article_ai",
        sa.Column(
            "article_id",
            sa.Uuid(),
            sa.ForeignKey("articles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("lang", sa.String(5), primary_key=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("article_ai")
