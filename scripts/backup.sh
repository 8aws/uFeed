#!/usr/bin/env bash
# Dump the uFeed Postgres database to ./backups/ufeed-<timestamp>.sql.gz, keep
# the newest BACKUP_KEEP locally and, if BACKUP_MIRROR_DIR is set in .env, copy
# each dump off the box (e.g. to a mounted QNAP share), keeping the newest
# BACKUP_MIRROR_KEEP there. Writes backups/status.json for the admin panel.
#
# If BACKUP_MIRROR_PASSPHRASE is set, off-box copies are encrypted with gpg
# (AES-256, integrity-protected) as ufeed-*.sql.gz.gpg and verified by
# decrypting them back; plaintext copies already on the mirror are encrypted
# in place. Local copies stay plain (they never leave this host; files are owner-only).
# Keep the passphrase somewhere else too (password manager): without it the
# off-box copies can't be restored.
#
# Usage: ./scripts/backup.sh   (stack must be up; safe to run from cron)
# Exit: 0 ok, 1 local dump failed, 2 dump ok but the off-box copy failed.
set -uo pipefail
umask 077 # dumps contain emails and password hashes: owner-only

cd "$(dirname "$0")/.."
mkdir -p backups
# Traverse-only for others: the unprivileged backend container can open
# status.json by name, but can't list the directory; dumps stay owner-only.
chmod 711 backups

env_get() { grep -E "^$1=" .env 2>/dev/null | tail -1 | cut -d= -f2-; }
POSTGRES_USER="$(env_get POSTGRES_USER)"; POSTGRES_USER="${POSTGRES_USER:-ufeed}"
POSTGRES_DB="$(env_get POSTGRES_DB)"; POSTGRES_DB="${POSTGRES_DB:-ufeed}"
KEEP="$(env_get BACKUP_KEEP)"; KEEP="${KEEP:-14}"
MIRROR="$(env_get BACKUP_MIRROR_DIR)"
MIRROR_KEEP="$(env_get BACKUP_MIRROR_KEEP)"; MIRROR_KEEP="${MIRROR_KEEP:-30}"
PASS="$(env_get BACKUP_MIRROR_PASSPHRASE)"
ENCRYPT=false
[ -n "$PASS" ] && ENCRYPT=true

# gpg with a throwaway home: nothing cached, no keyring touched; the
# passphrase goes through a file descriptor, never the command line.
GHOME="$(mktemp -d)"
trap 'gpgconf --homedir "$GHOME" --kill gpg-agent >/dev/null 2>&1; rm -rf "$GHOME"' EXIT
gpg_run() {
	gpg --homedir "$GHOME" --batch --yes --quiet --pinentry-mode loopback \
		--no-symkey-cache --passphrase-fd 3 "$@" 3< <(printf '%s' "$PASS")
}
encrypt_to() { # $1 plain file  $2 destination (.gpg)
	gpg_run --symmetric --cipher-algo AES256 --compress-algo none -o "$2" "$1"
}
verify_gpg() { # $1 encrypted dump: must decrypt with our passphrase to valid gzip
	gpg_run --decrypt "$1" 2>/dev/null | gzip -t 2>/dev/null
}

name="ufeed-$(date +%Y%m%d-%H%M%S).sql.gz"
out="backups/${name}"
started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# JSON-safe string (or null).
js() { if [ -z "${1:-}" ]; then printf 'null'; else printf '"%s"' "$(printf '%s' "$1" | tr -d '"\\' | tr '\n' ' ')"; fi; }
count() { ls -1 "$1"/ufeed-*.sql.gz 2>/dev/null | wc -l | tr -d ' '; }
mirror_ext() { if [ "$ENCRYPT" = true ]; then printf '.sql.gz.gpg'; else printf '.sql.gz'; fi; }

write_status() { # $1 ok  $2 error  $3 mirror_ok  $4 mirror_error
	local size=0
	[ -f "$out" ] && size="$(stat -c %s "$out" 2>/dev/null || stat -f %z "$out")"
	local mirror_json='{"enabled": false}'
	if [ -n "$MIRROR" ]; then
		local mcount=0
		[ "$3" = true ] && mcount="$(timeout 20 bash -c "ls -1 '$MIRROR'/ufeed-*$(mirror_ext) 2>/dev/null | wc -l" | tr -d ' ')"
		mirror_json="{\"enabled\": true, \"dir\": $(js "$MIRROR"), \"ok\": $3, \"error\": $(js "$4"), \"count\": ${mcount:-0}, \"keep\": $MIRROR_KEEP, \"encrypted\": $ENCRYPT}"
	fi
	cat > backups/status.json.tmp <<EOF
{"at": "$started", "ok": $1, "error": $(js "$2"), "file": $(js "$name"), "size_bytes": $size, "local_count": $(count backups), "keep": $KEEP, "mirror": $mirror_json}
EOF
	chmod 644 backups/status.json.tmp
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
	dest="$MIRROR/$name$( [ "$ENCRYPT" = true ] && printf '.gpg')"
	if ! timeout 20 mkdir -p "$MIRROR"; then
		mirror_ok=false; mirror_err="mirror not reachable: $MIRROR"
	elif [ "$ENCRYPT" = true ]; then
		# Encrypt locally, verify, then copy: the share only ever sees ciphertext.
		tmp="$GHOME/$name.gpg"
		if ! encrypt_to "$out" "$tmp" || ! verify_gpg "$tmp"; then
			mirror_ok=false; mirror_err="encryption failed"
		elif ! timeout 600 cp "$tmp" "$dest.part" || ! timeout 60 mv "$dest.part" "$dest"; then
			timeout 20 rm -f "$dest.part"
			mirror_ok=false; mirror_err="copy to mirror failed"
		elif [ "$(timeout 20 stat -c %s "$dest")" != "$(stat -c %s "$tmp")" ]; then
			mirror_ok=false; mirror_err="mirror copy size mismatch"
		fi
		rm -f "$tmp"
		# One-off upgrade: encrypt plaintext copies left from before encryption.
		if [ "$mirror_ok" = true ]; then
			for plain in $(timeout 20 bash -c "ls -1 '$MIRROR'/ufeed-*.sql.gz 2>/dev/null"); do
				t="$GHOME/$(basename "$plain").gpg"
				if timeout 600 cp "$plain" "$GHOME/plain.sql.gz" \
					&& encrypt_to "$GHOME/plain.sql.gz" "$t" && verify_gpg "$t" \
					&& timeout 600 cp "$t" "$plain.gpg.part" && timeout 60 mv "$plain.gpg.part" "$plain.gpg"; then
					timeout 20 rm -f "$plain"
					echo "$(date) encrypted old mirror copy $(basename "$plain")"
				else
					timeout 20 rm -f "$plain.gpg.part"
				fi
				rm -f "$t" "$GHOME/plain.sql.gz"
			done
		fi
	elif ! timeout 600 cp "$out" "$dest.part" || ! timeout 60 mv "$dest.part" "$dest"; then
		timeout 20 rm -f "$dest.part"
		mirror_ok=false; mirror_err="copy to mirror failed"
	elif [ "$(timeout 20 stat -c %s "$dest")" != "$(stat -c %s "$out")" ]; then
		mirror_ok=false; mirror_err="mirror copy size mismatch"
	fi
	if [ "$mirror_ok" = true ]; then
		timeout 60 bash -c "ls -1t '$MIRROR'/ufeed-*$(mirror_ext) | tail -n +$((MIRROR_KEEP + 1)) | xargs -r rm --"
		echo "$(date) mirrored to $dest"
	fi
	[ "$mirror_ok" = true ] || echo "$(date) MIRROR FAILED: $mirror_err"
fi

write_status true "" "$mirror_ok" "$mirror_err"
[ "$mirror_ok" = true ] || exit 2
