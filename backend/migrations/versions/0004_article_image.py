"""article lead image

Revision ID: 0004_article_image
Revises: 0003_favorites_analytics
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_article_image"
down_revision: str | None = "0003_favorites_analytics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("articles", sa.Column("image_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("articles", "image_url")
