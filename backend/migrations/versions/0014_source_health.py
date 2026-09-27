"""feed health (last error) + URL hygiene for stored feed links

Revision ID: 0014_source_health
Revises: 0013_moderation
Create Date: 2026-09-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_source_health"
down_revision: str | None = "0013_moderation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("last_error", sa.Text()))
    op.add_column("sources", sa.Column("last_error_at", sa.DateTime(timezone=True)))
    # Feed-supplied links are rendered as href/src; drop anything that isn't an
    # absolute http(s) URL (e.g. javascript:) stored before ingest validated it.
    op.execute("UPDATE articles SET url = NULL WHERE url IS NOT NULL AND url !~* '^https?://'")
    op.execute(
        "UPDATE articles SET image_url = NULL "
        "WHERE image_url IS NOT NULL AND image_url !~* '^https?://'"
    )
    op.execute(
        "UPDATE sources SET site_url = NULL WHERE site_url IS NOT NULL AND site_url !~* '^https?://'"
    )
    op.execute(
        "UPDATE sources SET favicon_url = NULL "
        "WHERE favicon_url IS NOT NULL AND favicon_url !~* '^https?://'"
    )


def downgrade() -> None:
    op.drop_column("sources", "last_error_at")
    op.drop_column("sources", "last_error")
