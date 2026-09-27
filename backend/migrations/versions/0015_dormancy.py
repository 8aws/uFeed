"""two-stage inactivity: deactivate (dormant) first, delete later

Revision ID: 0015_dormancy
Revises: 0014_source_health
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_dormancy"
down_revision: str | None = "0014_source_health"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("dormant_since", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("users", "dormant_since")
