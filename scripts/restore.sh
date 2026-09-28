#!/usr/bin/env bash
# Restore a uFeed Postgres dump created by backup.sh.
# Usage: ./scripts/restore.sh backups/ufeed-YYYYmmdd-HHMMSS.sql.gz
#        ./scripts/restore.sh /mnt/qnap/.../ufeed-YYYYmmdd-HHMMSS.sql.gz.gpg
# Encrypted (.gpg) off-box copies are decrypted with BACKUP_MIRROR_PASSPHRASE
# from .env, or gpg asks for the passphrase if it isn't there.
set -euo pipefail

cd "$(dirname "$0")/.."
file="${1:?usage: restore.sh <backup.sql.gz>}"

POSTGRES_USER="$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2 || echo ufeed)"
POSTGRES_DB="$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2 || echo ufeed)"

echo "Restoring $file into ${POSTGRES_DB:-ufeed} (existing data will be overwritten)..."
PASS="$(grep -E '^BACKUP_MIRROR_PASSPHRASE=' .env | tail -1 | cut -d= -f2- || true)"
decrypt() {
	if [ -n "$PASS" ]; then
		gpg --batch --quiet --pinentry-mode loopback --no-symkey-cache --passphrase-fd 3 \
			--decrypt "$file" 3< <(printf '%s' "$PASS")
	else
		gpg --quiet --decrypt "$file"
	fi
}
case "$file" in
*.gpg) decrypt | gunzip -c ;;
*) gunzip -c "$file" ;;
esac | docker compose exec -T db psql -U "${POSTGRES_USER:-ufeed}" "${POSTGRES_DB:-ufeed}"
echo "Done."
