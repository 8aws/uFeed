"""decode HTML entities left in article titles (feeds that encode them twice)

Revision ID: 0020_decode_titles
Revises: 0019_article_translations
Create Date: 2026-09-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.text import plain

revision: str = "0020_decode_titles"
down_revision: str | None = "0019_article_translations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PATTERN = r"&(#[0-9]+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);"


def upgrade() -> None:
    conn = op.get_bind()
    for table, col in (("articles", "title"), ("articles", "author"), ("sources", "title")):
        rows = conn.execute(
            sa.text(f"SELECT id, {col} FROM {table} WHERE {col} ~ :p"), {"p": PATTERN}
        ).all()
        for rid, value in rows:
            conn.execute(
                sa.text(f"UPDATE {table} SET {col} = :v WHERE id = :id"),
                {"v": plain(value), "id": rid},
            )
    # Translations and AI titles made from an encoded title: regenerate on demand.
    conn.execute(sa.text("DELETE FROM article_translations WHERE title ~ :p"), {"p": PATTERN})
    conn.execute(sa.text("DELETE FROM article_ai WHERE title ~ :p"), {"p": PATTERN})


def downgrade() -> None:
    pass  # data cleanup; nothing to undo
