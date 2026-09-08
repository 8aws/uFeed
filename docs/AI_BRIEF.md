# uFeed — Brief maestro para desarrollo paralelo con IA

> **Cómo usar este documento.** Es el contexto único y autocontenido del
> proyecto. Cada IA/agente que colabore debe recibir **todo** el bloque
> "PARTE A — Contexto común" + **solo el prompt de su frente** de la
> "PARTE B — Frentes de trabajo". Los contratos de la PARTE A son
> **inmutables sin acuerdo explícito**: son la interfaz entre frentes.

---

# PARTE A — Contexto común (dar a TODAS las IA)

## A.1 Qué construimos
uFeed: un lector de feeds RSS/Atom **autoalojado, multiusuario y multidioma
(EN/ES)**, inspirado en Feedly. Corre en un **contenedor Docker en un NAS** y
expone: backend, frontend web (PWA), API interna y **API pública** para acceder
al contenido desde fuera. La IA (resúmenes, dedup semántica, feeds inteligentes)
es una fase posterior, pero la arquitectura debe dejarle una costura limpia.

## A.2 Restricciones y objetivos
- Todo debe levantar con `docker compose up` en un NAS (recursos modestos).
- El servidor tiene **iGPU + NPU (Intel Core Ultra)**; la IA futura usará
  **OpenVINO** (CPU/iGPU/NPU) en un contenedor aparte. No implementar IA ahora,
  pero **no acoplar** el núcleo a ella.
- Multiusuario real con aislamiento de datos por usuario.
- i18n EN/ES desde el principio.

## A.3 Stack FIJO
- **Backend/API:** Python 3.12, **FastAPI**, SQLAlchemy 2.x async, Alembic,
  Pydantic v2, uvicorn.
- **Ingesta:** `feedparser` + `httpx` async.
- **BD:** PostgreSQL 16 (full-text `tsvector`; `pgvector` reservado para IA).
- **Cache/colas:** Redis.
- **Frontend:** SvelteKit + TypeScript, PWA (service worker), i18n.
- **Auth:** JWT access+refresh (web/app) y **API keys** con scopes (API pública).
- **Infra:** Docker Compose + Caddy (reverse-proxy, HTTPS).

## A.4 Principio de diseño CLAVE (no negociable)
Los feeds se descargan **una sola vez para todos**:
- `sources` y `articles` son **globales/compartidos**.
- El vínculo usuario↔fuente vive en `subscriptions`.
- El estado leído/guardado vive en `article_states` (por usuario+artículo).

## A.5 Estructura del repositorio (monorepo)
```
uFeed/
  backend/        # FastAPI: API interna + pública + worker de ingesta
    app/
      main.py
      core/       # config, seguridad, i18n, deps
      db/         # engine, session, base
      models/     # SQLAlchemy
      schemas/    # Pydantic
      api/        # routers (auth, sources, folders, articles, discover, public)
      services/   # lógica (ingesta, discovery, opml, search)
      workers/    # scheduler de ingesta
    migrations/   # Alembic
    tests/
    pyproject.toml
  Frontend/       # SvelteKit (PWA)
  API/            # contrato público: openapi.json exportado + SDK + docs
  App/            # reservado (nativa futura); PWA sale de Frontend/
  docs/
  docker-compose.yml
  .env.example
  Makefile
```
> `API/` es **solo contrato + SDK + documentación**, no un segundo servidor.

## A.6 Modelo de datos (CONTRATO — no cambiar sin acuerdo)
```
users            (id UUID PK, email UNIQUE, password_hash, locale ['en'|'es'],
                  is_active, created_at)
api_keys         (id UUID PK, user_id FK, key_hash, prefix, name,
                  scopes text[], last_used_at, created_at, revoked_at NULL)

sources          (id UUID PK, feed_url UNIQUE, site_url, title, favicon_url,
                  etag, last_modified, last_fetch_at, next_fetch_at,
                  fetch_interval_s DEFAULT 900, error_count, is_active)
articles         (id UUID PK, source_id FK, guid, url, title, author,
                  content_html, summary, lang, published_at, fetched_at,
                  UNIQUE(source_id, guid))

folders          (id UUID PK, user_id FK, name, position)
subscriptions    (id UUID PK, user_id FK, source_id FK, folder_id FK NULL,
                  custom_title NULL, created_at, UNIQUE(user_id, source_id))
article_states   (user_id FK, article_id FK, is_read bool, is_saved bool,
                  read_at NULL, PRIMARY KEY(user_id, article_id))
```
Índices mínimos: `articles(source_id, published_at DESC)`,
`article_states(user_id, is_read)`, FTS sobre `articles(title, content_html)`.

## A.7 Contrato de API (CONTRATO — interfaz backend↔frontend)
Base interna: `/api`. Base pública: `/api/v1` (auth por API key + rate-limit).
JSON en todo. Errores: `{ "error": { "code": str, "message": str } }`.
Paginación por cursor: `?cursor=&limit=` → `{ "items": [...], "next_cursor": str|null }`.
Idioma: header `Accept-Language: en|es`; `locale` persistido en `users`.

```
# Auth
POST   /api/auth/register     {email, password, locale?}     -> {user, tokens}
POST   /api/auth/login        {email, password}              -> {tokens}
POST   /api/auth/refresh      {refresh_token}                -> {tokens}
GET    /api/me                                               -> {user}
PATCH  /api/me                {locale?, ...}                 -> {user}

# API keys (para API pública)
GET    /api/keys                                             -> [{key meta}]
POST   /api/keys              {name, scopes[]}               -> {key once}
DELETE /api/keys/{id}

# Fuentes / carpetas
GET    /api/folders                                          -> [folder]
POST   /api/folders          {name}                          -> folder
PATCH  /api/folders/{id}     {name?, position?}
DELETE /api/folders/{id}
GET    /api/sources                                          -> [subscription+source]
POST   /api/sources          {url, folder_id?}               -> subscription
DELETE /api/sources/{id}     (unsubscribe)
POST   /api/discover         {url}                           -> [{feed_url,title}]
POST   /api/opml/import      (file)                          -> {imported, skipped}
GET    /api/opml/export                                      -> OPML file

# Artículos
GET    /api/articles?folder=&source=&unread=&saved=&q=&cursor=&limit=
                                                             -> paginado
GET    /api/articles/{id}                                    -> article
POST   /api/articles/{id}/read      / DELETE  (unread)
POST   /api/articles/{id}/save      / DELETE  (unsave)
POST   /api/articles/mark-all-read  {folder_id?|source_id?}

# API pública (mismos recursos de lectura, prefijo /api/v1, API key)
GET    /api/v1/articles ...    GET /api/v1/sources ...
GET    /openapi.json           # exportar a API/
```

## A.8 Convenciones (para TODAS las IA)
- **No romper** A.5/A.6/A.7 sin dejarlo escrito y avisar; son la interfaz.
- Python: `ruff` + `black`, type hints estrictos, `pytest`. Async en I/O.
- TS: `eslint` + `prettier`. Componentes pequeños y tipados.
- Todo endpoint nuevo: schema Pydantic + test + entrada en OpenAPI.
- Migraciones **siempre** vía Alembic (nunca DDL a mano).
- Secretos por `.env` (hay `.env.example`); nunca commitear secretos.
- Commits pequeños y descriptivos. Idiomas de UI: EN y ES (claves i18n, no texto
  hardcodeado).
- No implementar IA todavía; si un frente necesita "hueco" para IA, exponer una
  interfaz interna desactivable (`/ai/summarize`, `/ai/embed`) sin dependerla.

---

# PARTE B — Frentes de trabajo paralelizables

> Cada frente = un prompt independiente para una IA. **Orden de arranque:**
> WS0 primero (deja el andamiaje y los contratos en código). WS1–WS6 pueden ir
> en paralelo una vez WS0 está en `main`. WS7 es posterior.

## WS0 — Andamiaje + contratos (BLOQUEANTE, va primero)
**Prompt:** «Con la PARTE A como contexto, crea el andamiaje del monorepo:
`docker-compose.yml` (services: db=postgres16, cache=redis, backend, frontend,
proxy=caddy), `.env.example`, `Makefile` (up/down/logs/migrate/test/lint).
En `backend/` monta FastAPI con estructura A.5, config Pydantic-settings,
engine SQLAlchemy async, Alembic inicializado, y **todos los modelos de A.6**
con su primera migración. Define **todos los schemas Pydantic y los routers
vacíos (stubs 501)** de A.7 para congelar el contrato, y exporta `openapi.json`
a `API/`. Añade `/health`. Un `docker compose up` debe levantar todo y responder
`/health` y `/openapi.json`. Incluye README de arranque. **No implementes lógica
de negocio**, solo el esqueleto y los contratos.»
**Hecho cuando:** `docker compose up` verde, migración aplica, `/openapi.json`
refleja A.7, `make test`/`make lint` pasan en vacío.

## WS1 — Auth + usuarios + API keys
**Prompt:** «Sobre WS0, implementa registro/login/refresh con JWT
(access+refresh), hashing Argon2/bcrypt, `GET/PATCH /api/me` (incluye `locale`),
y la gestión de **API keys** (crear con scopes, listar meta, revocar; devolver
la clave en claro solo al crearla). Middleware/deps para autenticación por JWT
(interna) y por API key (pública). Tests de cada flujo. Respeta A.7.»
**Hecho cuando:** flujos auth con tests verdes; una API key válida autoriza en
`/api/v1/*`.

## WS2 — Worker de ingesta
**Prompt:** «Sobre WS0, implementa el worker de ingesta en `backend/app/workers`
+ `services/ingest.py`: planificador (APScheduler async) que recorre `sources`
activas por `next_fetch_at`, descarga con `httpx` usando `ETag`/`Last-Modified`,
parsea con `feedparser`, **deduplica** por `UNIQUE(source_id, guid)`, normaliza
fechas/charset/idioma, guarda `articles`, actualiza `etag/last_modified/
last_fetch_at/next_fetch_at`, y aplica **backoff exponencial** + `error_count`
en fallos. Respeta A.4 (descarga única compartida). Tests con feeds de ejemplo
(fixtures locales, sin red).»
**Hecho cuando:** dado un `source`, se ingieren artículos sin duplicados y el
scheduling respeta intervalos/backoff.

## WS3 — Fuentes, carpetas, suscripciones, artículos, búsqueda
**Prompt:** «Sobre WS0 (+depende de WS2 para datos), implementa la lógica de
`folders`, `sources`/`subscriptions` (suscribir por URL creando/reutilizando el
`source` global), `articles` (listado con filtros `folder/source/unread/saved/q`,
paginación por cursor, detalle), estados `read/save/unread/unsave` y
`mark-all-read`, y **búsqueda full-text** con `tsvector`. Respeta A.4 y A.7.
Tests de filtros y de aislamiento por usuario.»
**Hecho cuando:** un usuario suscribe un feed y navega/filtra/marca artículos;
el estado no se filtra entre usuarios.

## WS4 — Descubrimiento (autodetección + OPML)
**Prompt:** «Sobre WS0, implementa `POST /api/discover` (dada una URL de web,
detecta feeds vía `<link rel="alternate">` y heurísticas comunes
/feed,/rss,/atom.xml, devolviendo candidatos con título) e importación/exportación
**OPML** (`/api/opml/import` multipart, `/api/opml/export`). Reutiliza `sources`
existentes al importar. Tests con HTML/OPML fixtures.»
**Hecho cuando:** pegar la URL de un blog devuelve su feed; import/export OPML
ida y vuelta consistente.

## WS5 — Frontend (SvelteKit PWA + i18n)
**Prompt:** «Sobre el **contrato A.7** (no necesitas el backend real; usa el
`openapi.json` de `API/` y un cliente tipado + mocks), construye el lector en
`Frontend/` con SvelteKit + TS: login/registro, barra lateral (carpetas/fuentes),
lista de artículos (scroll infinito por cursor, marcar leído al vuelo, atajos de
teclado j/k/o), vista de artículo, guardar/leer, añadir fuente (usa /discover),
ajustes (idioma). PWA instalable con service worker y offline básico. i18n EN/ES
con claves (nada hardcodeado). Cliente API centralizado que respeta A.7 y
`Accept-Language`.»
**Hecho cuando:** flujo completo usable contra un backend real o mock; PWA
instala; cambio de idioma funciona.

## WS6 — Infra, seguridad de API pública y despliegue
**Prompt:** «Sobre WS0, endurece el despliegue: Caddy con HTTPS y rutas
(`/` → frontend, `/api` → backend), **rate-limiting** de `/api/v1` con Redis,
CORS, cabeceras de seguridad, healthchecks/depends_on en compose, perfiles
`dev`/`prod`, backups de Postgres, y CI (lint+test+build). Documenta el acceso
exterior por API en `API/README.md` + publica `openapi.json`. Deja preparado
(comentado) el passthrough `/dev/dri` y `/dev/accel` para el futuro contenedor
de IA.»
**Hecho cuando:** `prod` sirve HTTPS, la API pública tiene rate-limit, CI verde.

## WS7 — Servicio de IA (POSTERIOR, no bloqueante)
**Prompt:** «Diseña `ai/` como contenedor independiente detrás de una API interna
estable (`/ai/summarize`, `/ai/embed`, `/ai/dedup`) que el núcleo pueda tener
apagada. Prepara inferencia con **OpenVINO** para CPU/iGPU/NPU (Intel Core Ultra),
`pgvector` para embeddings, y passthrough de dispositivos en compose. Entrega
primero un stub funcional (respuestas dummy) y luego integra modelos.»
**Hecho cuando:** el núcleo llama al servicio si está activo y funciona igual si
está apagado; stub responde por iGPU/NPU cuando hay hardware.

---

# PARTE C — Reglas de coordinación entre IA
1. **La verdad está en el código de WS0** (modelos, schemas, `openapi.json`).
   Si un frente necesita cambiar un contrato de la PARTE A, debe: (a) proponerlo
   por escrito, (b) actualizar WS0 primero, (c) regenerar `openapi.json`.
2. Cada frente trabaja en su **rama** y toca **solo sus carpetas/archivos**
   (ver alcance en A.5). Evitar editar los stubs de otros frentes.
3. Todo PR: tests propios verdes + lint + no romper `openapi.json` ajeno.
4. Nada de IA fuera de WS7. Nada de secretos en el repo.
5. UI siempre por claves i18n (EN/ES).
