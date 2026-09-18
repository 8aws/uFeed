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

Once the box is running with `hashing`, switch the AI to the Intel iGPU/NPU:

1. Install the Intel compute runtime (`intel-opencl-icd`); confirm `/dev/dri`.
   For the NPU, install Intel's NPU driver, confirm `/dev/accel`, and uncomment
   `/dev/accel` in `compose.openvino.yml`.
2. Set `AI_BACKEND=openvino` in `.env`.
3. Recreate including the OpenVINO overlay:
   ```bash
   docker compose -f docker-compose.yml -f compose.prod.yml -f compose.openvino.yml up -d --build
   ```
4. Verify: `curl http://localhost:8001/health` shows `"backend":"openvino"`.
   Re-embedding/summarising happens gradually on the worker ticks
   (`OPENVINO_DEVICE` can be `AUTO`, `CPU`, `GPU` or `NPU`).

## 6. Backups

`pg_dump` to `./backups/` (keeps the last 14):
```bash
./scripts/backup.sh
```
Schedule it daily with cron:
```bash
(crontab -l 2>/dev/null; echo "30 4 * * * cd $PWD && ./scripts/backup.sh") | crontab -
```
Restore: `./scripts/restore.sh backups/ufeed-YYYYmmdd-HHMMSS.sql.gz`

## 7. Updating

```bash
git pull
docker compose -f docker-compose.yml -f compose.prod.yml up -d --build
# add -f compose.openvino.yml if you enabled OpenVINO
```
Migrations run automatically. Zero-config; the SPA is served fresh (the service
worker is network-first for navigations).

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
