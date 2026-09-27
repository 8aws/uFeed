# Deploying uFeed on the Beelink (production)

Target: a Beelink mini-PC with an Intel **Core Ultra** (iGPU + NPU), running
Linux + Docker. uFeed runs as a small Docker Compose stack.

TLS/domain are handled by **Cosmos on the QNAP** (external reverse proxy): uFeed
serves plain **HTTP** on a port of the Beelink, and Cosmos publishes the public
hostname + certificate and forwards to `http://<beelink-ip>:<port>`.

Two-step AI: start with the portable `hashing` backend (no drivers) to get
running fast, then switch to **OpenVINO** on the iGPU/NPU when ready.

## 0. Prerequisites (on the Beelink)

**Docker Engine + Compose plugin**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # log out/in afterwards
```

(Intel GPU/NPU drivers are only needed later, for OpenVINO — see step 5.)

## 1. Get the code and configure

```bash
git clone https://github.com/8aws/uFeed.git
cd uFeed
cp .env.prod.example .env
# Edit .env: POSTGRES_PASSWORD, JWT_SECRET (openssl rand -base64 36), the
# matching DATABASE_URL* passwords, and UFEED_HTTP_PORT (e.g. 8080).
# Keep UFEED_DOMAIN unset and AI_BACKEND=hashing for the first run.
```

## 2. Launch (HTTP, behind Cosmos)

```bash
docker compose -f docker-compose.yml -f compose.prod.yml up -d --build
```

- The backend runs Alembic migrations automatically on start.
- uFeed serves HTTP on `UFEED_HTTP_PORT` (e.g. 8080) — no certificate here.
- The worker begins polling feeds; the AI service embeds/summarises.

Check it on the box:
```bash
curl -s http://localhost:8080/health
docker compose logs -f backend worker ai
```

## 3. Expose it through Cosmos (QNAP)

In Cosmos, create a proxy / URL for your hostname (e.g. `feeds.example.com`):

- **Target**: `http://<beelink-lan-ip>:8080`
- Enable **HTTPS / Let's Encrypt** for the hostname in Cosmos (it terminates TLS).
- Make sure the Beelink's `UFEED_HTTP_PORT` is reachable from the QNAP on the LAN.

Then browse `https://feeds.example.com`.

## 4. First user

Open the site and use **Create account**. (Registration is open by default; see
"Pending" to restrict it.)

## 5. Enable OpenVINO (optional, later)

Once the box is running with `hashing`, switch the AI to the Intel iGPU/NPU.

**Key point:** the host having Intel drivers is not enough — the *container* is a
separate userland. Two things must line up: (a) the Intel **user-space runtime**
inside the AI image, and (b) the **device nodes** passed into the container.
The OpenVINO image build (`compose.openvino.yml`) installs the iGPU user-space
runtime for you; you only need the host driver + device nodes.

> **Wildcat Lake / Core Series 3 (this box):** brand-new silicon. The Intel
> runtime in apt (host *and* container) is too old to recognise its device IDs —
> that is why OpenVINO sees only CPU while the host kernel already drives it.
> Use the matched Intel releases: OpenVINO **2026.2**, compute-runtime (GPU)
> **26.22.38646.6**, Level Zero **1.28.2**, NPU driver **1.35.0+**. Put the
> container `.deb`s in `AI/intel-debs/` (see its README); the image installs them
> instead of the apt baseline. Check the current matrix at
> https://docs.openvino.ai/systemrequirements .

1. **Host (iGPU):** install a compute runtime new enough for the chip and
   confirm the node (for Wildcat Lake use Intel's latest `.deb`s from
   `intel/compute-runtime`, not distro apt):
   ```bash
   ls -l /dev/dri/renderD128                   # must exist
   ```
2. **Host (NPU, optional):** install Intel's `linux-npu-driver` (.debs matched to
   your kernel's `intel_vpu`), confirm `ls /dev/accel/accel0`, then uncomment the
   add `compose.npu.yml` to `COMPOSE_FILE` in `.env`.
3. Set `AI_BACKEND=openvino` and `OPENVINO_DEVICE=GPU` in `.env`. Use the **iGPU**
   for embeddings (~12× CPU, measured ~2700 emb/s on Wildcat Lake). Do **not**
   use the NPU here: it requires static shapes and sentence embeddings are
   dynamic (variable token length), so MiniLM won't run on it — the NPU is for
   static-shape models (e.g. YOLO/Frigate).
4. Rebuild including the OpenVINO overlay (the `--build` matters — it pulls the
   Intel runtime into the image):
   ```bash
   docker compose -f docker-compose.yml -f compose.prod.yml -f compose.openvino.yml up -d --build
   ```
5. **Verify what the runtime actually sees** (not just what was requested):
   ```bash
   docker compose exec backend curl -s http://ai:8001/health
   ```
   You want `"backend":"openvino"` and `available_devices` listing `GPU`
   (and `NPU` if enabled), e.g.
   `{"backend":"openvino","available_devices":["CPU","GPU"],"device_names":{...}}`.
   If it shows only `CPU`, the container can't reach the iGPU — check that
   `--build` ran against `compose.openvino.yml`, that `/dev/dri` is passed, and
   the group/GID note below.
6. **Permissions:** if `available_devices` omits `GPU` despite the node being
   passed, the container likely isn't in the host's `render` group. Find the
   host GID and add it in `compose.openvino.yml` under `group_add`:
   ```bash
   stat -c '%g' /dev/dri/renderD128   # e.g. 993 -> add "993" to group_add
   ```
   Re-embedding/summarising then happens gradually on the worker ticks.

## 6. Backups

`scripts/backup.sh` dumps Postgres to `./backups/` (verified with `gzip -t`,
keeps `BACKUP_KEEP`, default 14) and, if `BACKUP_MIRROR_DIR` is set in `.env`,
copies each dump off the box — e.g. a QNAP share mounted on this host — keeping
`BACKUP_MIRROR_KEEP` (default 30) there. Every step against the share is
time-boxed so a stale mount can't hang cron. It writes `backups/status.json`,
shown in **Settings → Administration → Backups** (with a warning if the last
backup is older than a day or the off-box copy failed).

```bash
./scripts/backup.sh          # exit 0 ok, 1 dump failed, 2 dump ok but mirror failed
```
Schedule it daily with cron:
```bash
(crontab -l 2>/dev/null; echo "30 4 * * * cd $PWD && ./scripts/backup.sh >> backups/backup.log 2>&1") | crontab -
```
Restore (local or mirrored file): `./scripts/restore.sh <path>/ufeed-YYYYmmdd-HHMMSS.sql.gz`

**Retention.** The worker purges old articles nightly (02:15 UTC) using the
window set in Administration (default 90 days, 0 = keep forever). Saved and
favourite articles, and the newest 50 of each feed, are always kept.

**Locked out?** If nobody can sign in (e.g. the only admin forgot the password):
```bash
docker compose -f docker-compose.yml -f compose.prod.yml exec backend \
  python -m app.scripts.reset_password you@example.com --admin
```
It prints a temporary password; you'll be asked to change it after signing in.

## 7. Updating

If the box can reach the repo:
```bash
git pull
docker compose -f docker-compose.yml -f compose.prod.yml up -d --build
# add -f compose.openvino.yml if you enabled OpenVINO
```

**Production (Beelink) is deployed from a workstation** — the private repo
can't be pulled on the box — with `scripts/deploy.sh`:

```bash
cp .deploy.env.example .deploy.env   # once: DEPLOY_HOST, DEPLOY_PATH, DEPLOY_PUBLIC_URL
scripts/deploy.sh                    # frontend backend worker
scripts/deploy.sh ai                 # also rebuild the AI image (keeps intel-debs)
```
It deploys `origin/main` only if CI is green for that commit, aborts if rsync
would delete anything on the box, never touches the box's `.env`, `backups/` or
`AI/intel-debs/*.deb`, validates the compose config, restarts, and checks the
backend, the AI device and the public URL.

Everything box-specific lives in the box's `.env` (nothing is hand-edited):
```bash
COMPOSE_FILE=docker-compose.yml:compose.prod.yml:compose.openvino.yml:compose.npu.yml
GPU_VIDEO_GID=44       # getent group video | cut -d: -f3
GPU_RENDER_GID=105     # stat -c %g /dev/dri/renderD128
```
With `COMPOSE_FILE` set, plain `docker compose ...` on the box uses the right
files. Drop `compose.npu.yml` from the list on hosts without `/dev/accel/accel0`.

Migrations run automatically. Zero-config; the SPA is served fresh (the service
worker is network-first for navigations).

## Security hardening (checklist)

Already in place in the app and stack:
- **SSRF guard**: every server-side fetch (feeds, discovery, og:image) and each
  redirect hop must resolve to public IPs; LAN/Docker/localhost are refused
  (`ALLOW_PRIVATE_FEEDS=true` only for trusted single-user installs).
- **XSS**: feed HTML is sanitised twice (feedparser server-side, DOMPurify in
  the reader); feed links/images are kept only if `http(s)`; a CSP
  (`script-src 'self'` + hashes) blocks injected scripts.
- **Auth**: bcrypt, per-IP rate limits on login/sign-up (real client IP via
  `TRUSTED_PROXIES`), sessions revoked on password change/reset, suspension,
  ban or deactivation; API keys hashed, scoped and rate-limited.
- **Proxy**: security headers, no `Server`/`Via`, 404 for scanner probes
  (`/.env`, `/.git`, `*.php`, …), `/docs` and `/openapi.json` off with `ENV=prod`.

On the box (`.env`):
```bash
ENV=prod
UFEED_HTTPS_BIND=127.0.0.1        # uFeed's own HTTPS port unused behind Cosmos
TRUSTED_PROXIES=<cosmos-ip>/32    # only the external proxy may set X-Forwarded-For
ALLOW_PRIVATE_FEEDS=false
```
and `chmod 600 .env` (backups are written owner-only by `backup.sh`).
Only `UFEED_HTTP_PORT` needs to be reachable, and only from the external
proxy — firewall it to that IP if the host's other services allow it.

## Notes / architecture

- Only the **proxy** publishes a port (`UFEED_HTTP_PORT`). Postgres and the
  backend bind to `127.0.0.1` and are otherwise reachable only on the internal
  Docker network. Consider firewalling `UFEED_HTTP_PORT` to the QNAP's LAN IP.
- Rate limiting (Redis) protects the public API and auth; security headers are
  set by Caddy.
- To verify OpenVINO picked the device: `docker compose logs ai` and
  `curl http://127.0.0.1:8001/health` inside the box shows the active backend.
  `OPENVINO_DEVICE` can be `AUTO`, `CPU`, `GPU` or `NPU`.

## Pending

- **User administration** (list/disable users, restrict open registration): not
  yet built. Self-service signup already works.
