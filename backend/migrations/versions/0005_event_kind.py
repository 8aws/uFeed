"""engagement event kind

Revision ID: 0005_event_kind
Revises: 0004_article_image
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_event_kind"
down_revision: str | None = "0004_article_image"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "read_events",
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="read"),
    )
    op.create_index("ix_read_events_kind", "read_events", ["kind"])


def downgrade() -> None:
    op.drop_index("ix_read_events_kind", table_name="read_events")
    op.drop_column("read_events", "kind")
