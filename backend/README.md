# uFeed backend

FastAPI application serving the internal API (`/api`), the public API
(`/api/v1`) and — from WS2 — the ingestion worker. See
[`../docs/AI_BRIEF.md`](../docs/AI_BRIEF.md) for the frozen contracts.

## Layout

```
app/
  main.py          # FastAPI app factory
  core/            # config (pydantic-settings), i18n
  db/              # async engine, session, declarative base
  models/          # SQLAlchemy models (A.6)
  schemas/         # Pydantic schemas (A.7)
  api/             # routers; routes/ holds one module per resource
  services/        # business logic (WS1–WS4)
  workers/         # ingestion (WS2)
  scripts/         # export_openapi.py
migrations/        # Alembic
tests/
```

Every route already exists and returns `501 not_implemented` so the OpenAPI
contract is frozen; workstreams fill in the bodies without changing signatures.

## Run with Docker (recommended)

From the repo root:

```bash
cp .env.example .env
make up          # builds + starts db, cache, backend, proxy; runs migrations
curl localhost:8000/health
curl localhost:8000/openapi.json
```

## Run locally (without Docker)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install ".[dev]"
# point DATABASE_URL_SYNC at a local Postgres, then:
alembic upgrade head
uvicorn app.main:app --reload
```

## Common tasks

```bash
make test        # pytest
make lint        # ruff + black --check
make openapi     # regenerate ../API/openapi.json
```
