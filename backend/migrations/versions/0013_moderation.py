"""account moderation: suspension, bans, activity tracking

Revision ID: 0013_moderation
Revises: 0012_passwords
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_moderation"
down_revision: str | None = "0012_passwords"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("suspended_until", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True)))
    # Start everyone's inactivity clock now so nobody is removed on deploy.
    op.execute("UPDATE users SET last_seen_at = now()")

    op.create_table(
        "bans",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("until", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.String(300)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_bans_email", "bans", ["email"])


def downgrade() -> None:
    op.drop_index("ix_bans_email", table_name="bans")
    op.drop_table("bans")
    op.drop_column("users", "last_seen_at")
    op.drop_column("users", "suspended_until")
