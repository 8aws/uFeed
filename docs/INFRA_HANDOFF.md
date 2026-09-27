# uFeed — infra handoff (Beelink)

Deploy uFeed on the Beelink. TLS + public hostname are handled **externally by
Cosmos on the QNAP**; uFeed serves plain **HTTP** on one host port that you pick.
You choose all host ports (env vars below) to avoid collisions.

## Repo
- GitHub: `https://github.com/8aws/uFeed` — branch `main`.
- Suggested location on the box: `/opt/ufeed` (any path is fine).

## What runs (Docker Compose, one project)
| Service   | Image / build      | Internal port | Published?                    |
|-----------|--------------------|---------------|-------------------------------|
| proxy     | Caddy              | 80            | **yes → `${UFEED_HTTP_PORT}`** (this is what Cosmos targets) |
| backend   | ./backend (FastAPI)| 8000          | localhost only `${BACKEND_HOST_PORT}` (debug; optional) |
| worker    | ./backend          | —             | no (ingest + AI passes)       |
| ai        | ./AI               | 8001          | no (internal)                 |
| db        | pgvector/pg16      | 5432          | localhost only `${DB_HOST_PORT}` (debug; optional) |
| cache     | redis:7            | 6379          | no                            |

Only **one** port needs to be reachable from the QNAP: `${UFEED_HTTP_PORT}`.
The two localhost-only ports are debug conveniences — pick free ones or ignore.

Named volumes (persist data): `pgdata`, `redis-data`, `caddy-data`,
`caddy-config`. Backups go to `./backups/`.

## Configure
```bash
git clone https://github.com/8aws/uFeed.git /opt/ufeed
cd /opt/ufeed
cp .env.prod.example .env
```
Set in `.env`:
- `POSTGRES_PASSWORD` — and the same password inside `DATABASE_URL` and
  `DATABASE_URL_SYNC` (format: `...://ufeed:<pwd>@db:5432/ufeed`).
- `JWT_SECRET` — `openssl rand -base64 36`.
- **Ports (you choose):** `UFEED_HTTP_PORT` (required, e.g. 8080),
  optionally `BACKEND_HOST_PORT` and `DB_HOST_PORT`.
- Leave `UFEED_DOMAIN` **unset/commented** (Cosmos does TLS).
- `AI_BACKEND=hashing` for the first boot (no Intel drivers needed).

## Launch (first run — portable AI, HTTP)
```bash
docker compose -f docker-compose.yml -f compose.prod.yml up -d --build
```
- Migrations run automatically on backend start.
- Health check on the box: `curl -s http://localhost:${UFEED_HTTP_PORT}/health`
  → `{"status":"ok",...}`
- Logs: `docker compose logs -f backend worker ai`

## Point Cosmos at it
- Cosmos proxy target: `http://<beelink-lan-ip>:${UFEED_HTTP_PORT}`
- Enable HTTPS/Let's Encrypt for the hostname in Cosmos.
- No app config needed for the domain; the SPA is same-origin and works behind
  the proxy over plain HTTP internally.

## Later: OpenVINO on iGPU/NPU (optional)
**The host's Intel drivers do NOT reach the container.** Two separate things:
the Intel **user-space runtime inside the image** (the OpenVINO build installs
the iGPU runtime for you) and the **device nodes passed in**.
1. Host iGPU: `intel-opencl-icd`, confirm `ls /dev/dri/renderD128`. NPU: install
   Intel's `linux-npu-driver`, confirm `/dev/accel/accel0`, then add
   `compose.npu.yml` to `COMPOSE_FILE` in `.env` (see docs/DEPLOY.md).
2. Set `AI_BACKEND=openvino` in `.env`.
3. `docker compose -f docker-compose.yml -f compose.prod.yml -f compose.openvino.yml up -d --build`
   (the `--build` is required — it bakes the Intel runtime into the AI image).
4. Verify what the runtime **actually** discovered:
   `docker compose exec backend curl -s http://ai:8001/health`
   → expect `"available_devices":["CPU","GPU"(,"NPU")]`. Only `CPU` means the
   container can't reach the iGPU (missing `--build` on the openvino overlay, or
   a group/GID permission issue — see `docs/DEPLOY.md` step 5).

## Updates & backups
- Update: `git pull && docker compose -f docker-compose.yml -f compose.prod.yml up -d --build`
  (add `-f compose.openvino.yml` if enabled). Migrations auto-apply.
- Backup (cron): `./scripts/backup.sh` (keeps 14). Restore:
  `./scripts/restore.sh backups/<file>.sql.gz`.

## Notes
- Requires Docker Engine + Compose plugin. First build pulls images + builds 3
  local images (backend, ai, frontend); needs outbound internet.
- Full runbook: `docs/DEPLOY.md`.
