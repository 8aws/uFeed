"""Plain-text helpers for feed fields."""

from __future__ import annotations

import html
import re

_ENTITY = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);")


def plain(value: str | None) -> str | None:
    """Decode HTML entities left in a plain-text field. Some feeds encode their
    titles twice (`Meta&#8217;s`, `&amp;#8217;`); two passes cover that without
    touching a literal ampersand."""
    if value is None:
        return None
    for _ in range(2):
        if not _ENTITY.search(value):
            break
        value = html.unescape(value)
    return value
