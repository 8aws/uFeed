"""mute sources and keywords

Revision ID: 0016_mutes
Revises: 0015_dormancy
Create Date: 2026-09-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_mutes"
down_revision: str | None = "0015_dormancy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("muted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "muted_keywords",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("keyword", sa.String(100), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "keyword", name="uq_muted_keyword"),
    )
    op.create_index("ix_muted_keywords_user_id", "muted_keywords", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_muted_keywords_user_id", table_name="muted_keywords")
    op.drop_table("muted_keywords")
    op.drop_column("subscriptions", "muted")
