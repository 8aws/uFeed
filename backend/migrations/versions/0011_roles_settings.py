"""user roles + instance settings

Revision ID: 0011_roles_settings
Revises: 0010_resummarize
Create Date: 2026-09-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0011_roles_settings"
down_revision: str | None = "0010_resummarize"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing accounts become "general"; the oldest account is the admin.
    op.add_column(
        "users",
        sa.Column("role", sa.String(16), nullable=False, server_default="general"),
    )
    op.execute(
        "UPDATE users SET role = 'admin' "
        "WHERE id = (SELECT id FROM users ORDER BY created_at ASC LIMIT 1)"
    )
    # New accounts get their role from app code (default "free").
    op.alter_column("users", "role", server_default="free")

    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", JSONB, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_column("users", "role")
