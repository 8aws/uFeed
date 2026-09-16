"""full-text search index on articles

Revision ID: 0002_articles_fts
Revises: 0001_initial
Create Date: 2026-09-15
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002_articles_fts"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# 'simple' config: no language-specific stemming, so it behaves consistently
# across EN/ES content. Must match app.services.articles._fts_vector exactly.
_FTS_EXPR = "to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content_html, ''))"


def upgrade() -> None:
    op.execute(f"CREATE INDEX ix_articles_fts ON articles USING gin ({_FTS_EXPR})")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_articles_fts")
