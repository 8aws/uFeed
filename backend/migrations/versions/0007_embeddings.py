"""pgvector embeddings on articles

Revision ID: 0007_embeddings
Revises: 0006_display_name
Create Date: 2026-09-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0007_embeddings"
down_revision: str | None = "0006_display_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("articles", sa.Column("embedding", Vector(DIM), nullable=True))
    # Cosine-distance ANN index (vectors are L2-normalised by the AI service).
    op.execute(
        "CREATE INDEX ix_articles_embedding ON articles "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_articles_embedding")
    op.drop_column("articles", "embedding")
