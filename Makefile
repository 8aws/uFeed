.PHONY: help up down logs build migrate makemigration revision test lint fmt openapi shell

help:
	@echo "uFeed — common tasks"
	@echo "  make up        - start the full stack (docker compose up --build -d)"
	@echo "  make down      - stop the stack"
	@echo "  make logs      - tail all logs"
	@echo "  make migrate   - apply DB migrations (alembic upgrade head)"
	@echo "  make revision  - autogenerate a migration (m=\"message\")"
	@echo "  make test      - run backend tests"
	@echo "  make lint      - ruff + black --check"
	@echo "  make fmt       - ruff --fix + black"
	@echo "  make openapi   - export API/openapi.json from the app"

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

build:
	docker compose build

migrate:
	docker compose exec backend alembic upgrade head

revision:
	docker compose exec backend alembic revision --autogenerate -m "$(m)"

test:
	cd backend && python -m pytest -q

lint:
	cd backend && ruff check . && black --check .

fmt:
	cd backend && ruff check --fix . && black .

openapi:
	cd backend && python -m app.scripts.export_openapi

backup:
	./scripts/backup.sh

restore:
	./scripts/restore.sh $(f)

shell:
	docker compose exec backend sh
