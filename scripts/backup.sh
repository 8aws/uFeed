#!/usr/bin/env bash
# Dump the uFeed Postgres database to ./backups/ufeed-<timestamp>.sql.gz, keep
# the newest BACKUP_KEEP locally and, if BACKUP_MIRROR_DIR is set in .env, copy
# each dump off the box (e.g. to a mounted QNAP share), keeping the newest
# BACKUP_MIRROR_KEEP there. Writes backups/status.json for the admin panel.
#
# Usage: ./scripts/backup.sh   (stack must be up; safe to run from cron)
# Exit: 0 ok, 1 local dump failed, 2 dump ok but the off-box copy failed.
set -uo pipefail

cd "$(dirname "$0")/.."
mkdir -p backups

env_get() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2-; }
POSTGRES_USER="$(env_get POSTGRES_USER)"; POSTGRES_USER="${POSTGRES_USER:-ufeed}"
POSTGRES_DB="$(env_get POSTGRES_DB)"; POSTGRES_DB="${POSTGRES_DB:-ufeed}"
KEEP="$(env_get BACKUP_KEEP)"; KEEP="${KEEP:-14}"
MIRROR="$(env_get BACKUP_MIRROR_DIR)"
MIRROR_KEEP="$(env_get BACKUP_MIRROR_KEEP)"; MIRROR_KEEP="${MIRROR_KEEP:-30}"

name="ufeed-$(date +%Y%m%d-%H%M%S).sql.gz"
out="backups/${name}"
started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# JSON-safe string (or null).
js() { if [ -z "${1:-}" ]; then printf 'null'; else printf '"%s"' "$(printf '%s' "$1" | tr -d '"\\' | tr '\n' ' ')"; fi; }
count() { ls -1 "$1"/ufeed-*.sql.gz 2>/dev/null | wc -l | tr -d ' '; }

write_status() { # $1 ok  $2 error  $3 mirror_ok  $4 mirror_error
	local size=0
	[ -f "$out" ] && size="$(stat -c %s "$out" 2>/dev/null || stat -f %z "$out")"
	local mirror_json='{"enabled": false}'
	if [ -n "$MIRROR" ]; then
		local mcount=0
		[ "$3" = true ] && mcount="$(timeout 20 bash -c "ls -1 '$MIRROR'/ufeed-*.sql.gz 2>/dev/null | wc -l" | tr -d ' ')"
		mirror_json="{\"enabled\": true, \"dir\": $(js "$MIRROR"), \"ok\": $3, \"error\": $(js "$4"), \"count\": ${mcount:-0}, \"keep\": $MIRROR_KEEP}"
	fi
	cat > backups/status.json.tmp <<EOF
{"at": "$started", "ok": $1, "error": $(js "$2"), "file": $(js "$name"), "size_bytes": $size, "local_count": $(count backups), "keep": $KEEP, "mirror": $mirror_json}
EOF
	mv backups/status.json.tmp backups/status.json
}

# 1) Dump + verify (never leave a truncated file behind).
if ! docker compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$out.tmp" \
	|| ! gzip -t "$out.tmp" 2>/dev/null \
	|| [ "$(stat -c %s "$out.tmp" 2>/dev/null || stat -f %z "$out.tmp")" -lt 1024 ]; then
	rm -f "$out.tmp"
	echo "$(date) backup FAILED"
	write_status false "pg_dump failed" false "skipped: local dump failed"
	exit 1
fi
mv "$out.tmp" "$out"
echo "$(date) wrote $out"
ls -1t backups/ufeed-*.sql.gz | tail -n +$((KEEP + 1)) | xargs -r rm --

# 2) Off-box copy. Every step is time-boxed: a network share can hang.
mirror_ok=true
mirror_err=""
if [ -n "$MIRROR" ]; then
	if ! timeout 20 mkdir -p "$MIRROR"; then
		mirror_ok=false; mirror_err="mirror not reachable: $MIRROR"
	elif ! timeout 600 cp "$out" "$MIRROR/$name.part" \
		|| ! timeout 60 mv "$MIRROR/$name.part" "$MIRROR/$name"; then
		timeout 20 rm -f "$MIRROR/$name.part"
		mirror_ok=false; mirror_err="copy to mirror failed"
	elif [ "$(timeout 20 stat -c %s "$MIRROR/$name")" != "$(stat -c %s "$out")" ]; then
		mirror_ok=false; mirror_err="mirror copy size mismatch"
	else
		timeout 60 bash -c "ls -1t '$MIRROR'/ufeed-*.sql.gz | tail -n +$((MIRROR_KEEP + 1)) | xargs -r rm --"
		echo "$(date) mirrored to $MIRROR/$name"
	fi
	[ "$mirror_ok" = true ] || echo "$(date) MIRROR FAILED: $mirror_err"
fi

write_status true "" "$mirror_ok" "$mirror_err"
[ "$mirror_ok" = true ] || exit 2
