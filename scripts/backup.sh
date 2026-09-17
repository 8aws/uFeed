#!/usr/bin/env bash
# Dump the uFeed Postgres database to ./backups/ufeed-<timestamp>.sql.gz
# Usage: ./scripts/backup.sh   (run from the repo root, stack must be up)
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p backups
ts="$(date +%Y%m%d-%H%M%S)"
out="backups/ufeed-${ts}.sql.gz"

# shellcheck disable=SC1091
POSTGRES_USER="$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2 || echo ufeed)"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2 || echo ufeed)"

docker compose exec -T db pg_dump -U "${POSTGRES_USER:-ufeed}" "${POSTGRES_DB:-ufeed}" \
	| gzip > "$out"

echo "Wrote $out"
# Keep the 14 most recent backups.
ls -1t backups/ufeed-*.sql.gz | tail -n +15 | xargs -r rm --
