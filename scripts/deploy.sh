#!/usr/bin/env bash
# Deploy origin/main to the production box. The box can't pull the private
# repo, so this runs on a workstation: fresh checkout -> rsync -> build/restart
# on the box -> health checks.
#
# Usage:  scripts/deploy.sh [--skip-ci] [--allow-delete] [service ...]
#         default services: frontend backend worker   (add "ai" to rebuild AI)
# Config: .deploy.env (gitignored; see .deploy.env.example)
#
# Safety rails:
#   - refuses to deploy a commit whose CI isn't green (unless --skip-ci)
#   - aborts if rsync would delete anything on the box (unless --allow-delete,
#     e.g. when a file moved in the repo; the list is always printed)
#   - never touches the box's .env, backups/ or AI/intel-debs/*.deb
#   - validates the box's compose config before restarting
set -euo pipefail

cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
[ -f .deploy.env ] && . ./.deploy.env
: "${DEPLOY_HOST:?set DEPLOY_HOST (user@host) in .deploy.env}"
: "${DEPLOY_PATH:?set DEPLOY_PATH in .deploy.env}"
REPO="${DEPLOY_REPO:-8aws/uFeed}"
SRC="${DEPLOY_CACHE:-$HOME/.cache/ufeed-deploy}"

skip_ci=0
allow_delete=0
services=()
for arg in "$@"; do
	case "$arg" in
	--skip-ci) skip_ci=1 ;;
	--allow-delete) allow_delete=1 ;;
	-*) echo "unknown option $arg" >&2; exit 64 ;;
	*) services+=("$arg") ;;
	esac
done
[ ${#services[@]} -gt 0 ] || services=(frontend backend worker)

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }

# 1) Fresh copy of origin/main (a cache dir outside /tmp, which macOS purges).
if [ -d "$SRC/.git" ]; then
	git -C "$SRC" fetch -q origin
	git -C "$SRC" reset -q --hard origin/main
	git -C "$SRC" clean -qfdx
else
	mkdir -p "$(dirname "$SRC")"
	gh repo clone "$REPO" "$SRC" -- -q
fi
sha="$(git -C "$SRC" rev-parse HEAD)"
say "Deploying $(git -C "$SRC" log --oneline -1)"

# 2) CI must be green for this exact commit.
if [ "$skip_ci" -eq 0 ]; then
	ci="$(gh run list -R "$REPO" --commit "$sha" --json status,conclusion \
		-q '.[0] | (.status + "/" + (.conclusion // ""))')"
	if [ "$ci" != "completed/success" ]; then
		echo "CI for ${sha:0:7} is '${ci:-none}' — aborting (use --skip-ci to override)." >&2
		exit 1
	fi
	say "CI green for ${sha:0:7}"
fi

# 3) The box must be configured through its .env (no hand-edited compose files).
if ! ssh "$DEPLOY_HOST" "grep -q '^COMPOSE_FILE=' '$DEPLOY_PATH/.env'"; then
	echo "The box's .env has no COMPOSE_FILE — see docs/DEPLOY.md (Configure)." >&2
	exit 1
fi

# 4) Sync, refusing to delete anything unexpected on the box.
excludes=(--exclude=.git --exclude=.env --exclude=.deploy.env --exclude=backups
	--exclude='AI/intel-debs/*.deb')
deleting="$(rsync -a --delete --dry-run --itemize-changes "${excludes[@]}" \
	"$SRC/" "$DEPLOY_HOST:$DEPLOY_PATH/" | grep '^\*deleting' || true)"
if [ -n "$deleting" ]; then
	echo "rsync will delete on the box:" >&2
	echo "$deleting" >&2
	if [ "$allow_delete" -ne 1 ]; then
		echo "aborting (re-run with --allow-delete if these are expected)." >&2
		exit 1
	fi
fi
rsync -a --delete "${excludes[@]}" "$SRC/" "$DEPLOY_HOST:$DEPLOY_PATH/"
say "Synced to $DEPLOY_HOST:$DEPLOY_PATH"

# 5) Validate, build and restart on the box (compose files come from COMPOSE_FILE).
ssh "$DEPLOY_HOST" "cd '$DEPLOY_PATH' && docker compose config -q \
	&& docker compose build ${services[*]} && docker compose up -d" </dev/null
# The proxy's Caddyfile is bind-mounted: reload it so config changes apply.
ssh "$DEPLOY_HOST" "cd '$DEPLOY_PATH' && docker compose exec -T proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile" </dev/null
say "Built and restarted: ${services[*]} (proxy config reloaded)"

# 6) Health: backend (inside the network), AI device, and the public URL.
ssh "$DEPLOY_HOST" "cd '$DEPLOY_PATH' && for i in \$(seq 1 40); do \
	docker compose exec -T backend python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" \
	2>/dev/null && break; sleep 2; done && echo 'backend: healthy' && \
	docker compose exec -T backend python -c \"import json, urllib.request; \
d = json.load(urllib.request.urlopen('http://ai:8001/health')); print('ai:', d['backend'], d['device'], d.get('available_devices'))\"" </dev/null
if [ -n "${DEPLOY_PUBLIC_URL:-}" ]; then
	code="$(curl -sk -o /dev/null -w '%{http_code}' "$DEPLOY_PUBLIC_URL/health")"
	echo "public $DEPLOY_PUBLIC_URL/health: $code"
	[ "$code" = 200 ] || { echo "public health check failed" >&2; exit 1; }
fi
say "Done: ${sha:0:7}"
