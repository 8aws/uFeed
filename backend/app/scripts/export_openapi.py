"""Export the OpenAPI schema to API/openapi.json (the public contract).

Run: python -m app.scripts.export_openapi
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

# repo_root/backend/app/scripts/export_openapi.py -> repo_root
REPO_ROOT = Path(__file__).resolve().parents[3]
OUT = REPO_ROOT / "API" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(REPO_ROOT)} ({len(schema.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
