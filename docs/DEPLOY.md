# Deploying uFeed on the Beelink (production)

Target: a Beelink mini-PC with an Intel **Core Ultra** (iGPU + NPU), running
Linux + Docker. uFeed runs as a small Docker Compose stack; the AI service uses
**OpenVINO** on the iGPU/NPU. Everything is reached through the Caddy reverse
proxy over HTTPS.

## 0. Prerequisites (on the Beelink)

1. **Docker Engine + Compose plugin**
   ```bash
   curl -fsSL https://get.docker.com | sh
   sudo usermod -aG docker "$USER"   # log out/in afterwards
   ```
2. **Intel GPU / NPU runtime** (only needed for `AI_BACKEND=openvino`):
   - iGPU: install `intel-opencl-icd` (compute runtime). Confirm `/dev/dri`
     exists (`ls /dev/dri`).
   - NPU (Core Ultra): install Intel's NPU driver; confirm `/dev/accel` exists,
     then uncomment the `/dev/accel` device in `compose.prod.yml`.
   - If you skip this, set `AI_BACKEND=hashing` — everything works, just without
     semantic-quality embeddings/summaries.
3. A **DNS record** pointing your hostname (e.g. `feeds.example.com`) at the box,
   with ports **80 and 443** reachable (Caddy needs 80/443 for HTTPS).

## 1. Get the code and configure

```bash
git clone https://github.com/8aws/uFeed.git
cd uFeed
cp .env.prod.example .env
# Edit .env: set POSTGRES_PASSWORD, JWT_SECRET (openssl rand -base64 36),
# UFEED_DOMAIN and the matching DATABASE_URL* passwords.
```

## 2. Launch

```bash
docker compose -f docker-compose.yml -f compose.prod.yml up -d --build
```

- The backend runs Alembic migrations automatically on start.
- Caddy obtains a Let's Encrypt certificate for `UFEED_DOMAIN` on first run.
- The worker begins polling feeds; the AI service embeds/summarises in the
  background.

Check it:
```bash
curl -s https://feeds.example.com/health
docker compose logs -f backend worker ai
```

## 3. First user

Open `https://feeds.example.com` and use **Create account**. (Registration is
open by default; see "User administration" below to restrict it — planned.)

## 4. Backups

`pg_dump` to `./backups/` (keeps the last 14):
```bash
./scripts/backup.sh
```
Schedule it daily with cron:
```bash
(crontab -l 2>/dev/null; echo "30 4 * * * cd $PWD && ./scripts/backup.sh") | crontab -
```
Restore: `./scripts/restore.sh backups/ufeed-YYYYmmdd-HHMMSS.sql.gz`

## 5. Updating

```bash
git pull
docker compose -f docker-compose.yml -f compose.prod.yml up -d --build
```
Migrations run automatically. Zero-config; the SPA is served fresh (the service
worker is network-first for navigations).

## Notes / architecture

- Only the **proxy** publishes ports (80/443). Postgres and the backend are
  bound to `127.0.0.1` in the base compose and otherwise reachable only on the
  internal Docker network.
- Rate limiting (Redis) protects the public API and auth; security headers are
  set by Caddy.
- To verify OpenVINO picked the device: `docker compose logs ai` and
  `curl http://127.0.0.1:8001/health` inside the box shows the active backend.
  `OPENVINO_DEVICE` can be `AUTO`, `CPU`, `GPU` or `NPU`.

## Pending

- **User administration** (list/disable users, restrict open registration): not
  yet built. Self-service signup already works.
