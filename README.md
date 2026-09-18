# uFeed

Lector de feeds RSS/Atom **autoalojado, multiusuario y multidioma (EN/ES)**,
inspirado en Feedly. Pensado para ejecutarse en un contenedor Docker en un NAS,
exponiendo backend, frontend web (PWA), API interna y **API pública** para
acceder al contenido desde fuera. La capa de IA (resúmenes, deduplicación
semántica, feeds inteligentes) es una fase posterior, preparada para correr con
**OpenVINO** sobre iGPU/NPU (Intel Core Ultra).

## Estado

Fase de planificación. El diseño y la hoja de ruta están en `docs/`.

- [`docs/PLAN.md`](docs/PLAN.md) — arquitectura y hoja de ruta por fases.
- [`docs/AI_BRIEF.md`](docs/AI_BRIEF.md) — brief maestro para desarrollo
  paralelo con varias IA (contratos comunes + prompts por frente de trabajo).
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — despliegue en producción (Beelink,
  Docker Compose, OpenVINO iGPU/NPU, HTTPS, backups).

## Producción (resumen)

```bash
cp .env.prod.example .env   # editar secretos + UFEED_DOMAIN
docker compose -f docker-compose.yml -f compose.prod.yml up -d --build
```

## Estructura

```
backend/   # FastAPI: API interna + pública + worker de ingesta
Frontend/  # SvelteKit (PWA)
API/       # contrato público: openapi.json + SDK + documentación
App/       # reservado (app nativa futura)
docs/      # planificación y briefs
```

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2 (async) · PostgreSQL 16 · Redis ·
SvelteKit · Docker Compose · Caddy.
