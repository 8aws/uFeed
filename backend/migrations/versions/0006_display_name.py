"""user display name

Revision ID: 0006_display_name
Revises: 0005_event_kind
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_display_name"
down_revision: str | None = "0005_event_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "display_name")
