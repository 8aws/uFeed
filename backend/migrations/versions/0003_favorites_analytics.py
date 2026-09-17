"""favorites, article word_count/tags, and read events

Revision ID: 0003_favorites_analytics
Revises: 0002_articles_fts
Create Date: 2026-09-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_favorites_analytics"
down_revision: str | None = "0002_articles_fts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "article_states",
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("articles", sa.Column("word_count", sa.Integer(), nullable=True))
    op.add_column(
        "articles",
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=False, server_default="{}"),
    )
    op.create_index("ix_article_states_user_fav", "article_states", ["user_id", "is_favorite"])

    op.create_table(
        "read_events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("article_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("dwell_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_read_events_article", "read_events", ["article_id"])
    op.create_index("ix_read_events_created", "read_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("read_events")
    op.drop_index("ix_article_states_user_fav", table_name="article_states")
    op.drop_column("articles", "tags")
    op.drop_column("articles", "word_count")
    op.drop_column("article_states", "is_favorite")
