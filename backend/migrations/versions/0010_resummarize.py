"""clear ai_summary so it regenerates with the whole-document summarizer

Revision ID: 0010_resummarize
Revises: 0009_dedup
Create Date: 2026-09-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0010_resummarize"
down_revision: str | None = "0009_dedup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Old summaries were just the article's opening sentences. Clear them so the
    # worker regenerates them (gradually, per tick) with the new whole-document
    # extractive summarizer.
    op.execute("UPDATE articles SET ai_summary = NULL")


def downgrade() -> None:
    # Summaries are derived data; nothing to restore.
    pass
