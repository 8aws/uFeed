#!/usr/bin/env bash
# Restore a uFeed Postgres dump created by backup.sh.
# Usage: ./scripts/restore.sh backups/ufeed-YYYYmmdd-HHMMSS.sql.gz
set -euo pipefail

cd "$(dirname "$0")/.."
file="${1:?usage: restore.sh <backup.sql.gz>}"

POSTGRES_USER="$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2 || echo ufeed)"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2 || echo ufeed)"

echo "Restoring $file into ${POSTGRES_DB:-ufeed} (existing data will be overwritten)..."
gunzip -c "$file" | docker compose exec -T db psql -U "${POSTGRES_USER:-ufeed}" "${POSTGRES_DB:-ufeed}"
echo "Done."
