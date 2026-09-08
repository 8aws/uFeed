# uFeed — Plan de arquitectura y hoja de ruta

> Lector de feeds RSS/Atom autoalojado, multiusuario y multidioma (EN/ES),
> pensado para ejecutarse en un contenedor de un NAS (Docker), con backend,
> frontend, API pública y app (PWA primero). Inspirado en Feedly.

Estado: **borrador de planificación** (aún no se ha escrito código de producto).

---

## 1. Decisiones tomadas

| Tema | Decisión |
|---|---|
| Alcance MVP | Núcleo + descubrimiento (autodetección de feeds, OPML, búsqueda) |
| Backend/API | Python + **FastAPI** (async, OpenAPI automático) |
| App | **PWA** primero; nativa se decide más adelante |
| Idiomas | EN y ES desde el día 1 |
| Despliegue | **Docker Compose** en NAS |
| IA | **Fase posterior**, pero con arquitectura preparada. Server con **iGPU + NPU** → objetivo **OpenVINO** (CPU/iGPU/NPU) |

---

## 2. Principio de diseño clave: fuentes y artículos compartidos

Para que escale con varios usuarios y muchos feeds:

- **Un feed se descarga UNA vez** para todos los usuarios (no N veces).
- `sources` y `articles` son **globales**.
- El vínculo usuario↔fuente vive en `subscriptions`.
- El estado leído/guardado vive en `article_states` (por usuario y artículo).

Esto resuelve de golpe la deduplicación de descargas y acota el crecimiento
del estado por usuario.

---

## 3. Arquitectura de contenedores

```
┌─────────────────────────────────────────────────────────┐
│                      NAS (Docker)                         │
│                                                           │
│  [reverse-proxy]  Caddy/Traefik  → HTTPS + acceso ext.    │
│        │                                                  │
│        ├──► [frontend]  SvelteKit (PWA)                   │
│        │                                                  │
│        └──► [backend]   FastAPI  (API interna + pública)  │
│                 │                                         │
│                 ├──► [db]      PostgreSQL                 │
│                 ├──► [cache]   Redis (colas + rate-limit) │
│                 │                                         │
│  [worker]  ingesta de feeds (APScheduler/Celery)         │
│                 │                                         │
│  [ai] (Fase 5)  servicio OpenVINO  ─ /dev/dri /dev/accel │
└─────────────────────────────────────────────────────────┘
```

### Mapeo a las carpetas actuales del repo
- `backend/`  → app FastAPI (API interna **y** pública) + worker de ingesta.
- `Frontend/` → SvelteKit (PWA).
- `API/`      → **contrato público**: spec OpenAPI exportada, documentación
  para consumidores externos y SDK/cliente generado. *(No es un segundo
  servidor; la API la sirve `backend/`.)*
- `App/`      → reservado; de momento la PWA sale de `Frontend/`.

> A decidir: si `API/` se queda solo como documentación/SDK o si en el futuro
> se convierte en un gateway independiente. Recomendación: **solo contrato +
> SDK** al principio.

---

## 4. Stack técnico

- **Backend:** FastAPI, SQLAlchemy 2.x (async), Alembic (migraciones),
  Pydantic v2, `uvicorn`.
- **Ingesta:** `feedparser` + `httpx` (async) con soporte `ETag`/`Last-Modified`,
  backoff exponencial y detección de feeds rotos. Planificación con APScheduler
  (simple) o Celery+Redis (si crece).
- **BD:** PostgreSQL 16 (full-text nativo con `tsvector`; `pgvector` reservado
  para la Fase 5 de IA).
- **Cache/colas:** Redis (rate-limiting de API pública, colas de ingesta).
- **Frontend:** SvelteKit + TypeScript, i18n (`typesafe-i18n` o `svelte-i18n`),
  service worker para PWA (offline básico).
- **Auth:** JWT (access + refresh) para la app/web; **API keys** con scopes para
  el acceso externo.
- **Infra:** Docker Compose, Caddy (HTTPS automático) como reverse-proxy.

---

## 5. Modelo de datos (borrador)

```
users            (id, email, password_hash, locale, created_at)
api_keys         (id, user_id, key_hash, name, scopes, last_used, created_at)

sources          (id, feed_url UNIQUE, site_url, title, favicon,
                  etag, last_modified, last_fetch_at, next_fetch_at,
                  fetch_interval_s, error_count, is_active)
articles         (id, source_id→sources, guid, url, title, author,
                  content_html, summary, lang, published_at, fetched_at)
                 UNIQUE(source_id, guid)

folders          (id, user_id→users, name, position)
subscriptions    (id, user_id→users, source_id→sources, folder_id→folders,
                  custom_title, created_at)
                 UNIQUE(user_id, source_id)
article_states   (user_id→users, article_id→articles, is_read, is_saved,
                  read_at)  PRIMARY KEY(user_id, article_id)

tags             (id, user_id, name)              # opcional
article_tags     (article_id, tag_id, user_id)    # opcional
```

Índices clave: `articles(source_id, published_at)`, `article_states(user_id,
is_read)`, full-text sobre `articles(title, content)`.

---

## 6. Superficie de API (borrador)

Interna (web/app, JWT) y pública (API keys) comparten el mismo esquema REST:

```
POST   /auth/register            /auth/login            /auth/refresh
GET    /me                       PATCH /me   (locale, etc.)

GET    /sources                  POST /sources (subscribe por url/feed)
DELETE /sources/{id}
POST   /discover      {url}      → detecta feeds candidatos en una web
POST   /opml/import              GET  /opml/export

GET    /folders  POST  PATCH  DELETE
GET    /articles?folder=&source=&unread=&saved=&q=&cursor=
POST   /articles/{id}/read       /articles/{id}/save   (+ unread/unsave)
POST   /articles/mark-all-read   {folder|source}

# API pública añade:
GET    /v1/...   (mismos recursos, auth por API key + rate-limit)
GET    /openapi.json   (contrato → carpeta API/)
```

Multidioma: `Accept-Language` en la API; `locale` persistido en `users`.

---

## 7. Hoja de ruta por fases

### Fase 0 — Andamiaje (base)
- Estructura del monorepo, `docker-compose.yml`, `.env`, Makefile.
- FastAPI "hola mundo" + Postgres + Redis + Alembic + healthchecks.
- Reverse-proxy Caddy con HTTPS local.
- **Salida:** `docker compose up` levanta todo y responde `/health`.

### Fase 1 — Núcleo
- Modelo de datos + migraciones.
- Auth (registro/login/refresh, JWT).
- Worker de ingesta (poll, ETag/Last-Modified, dedup, backoff).
- CRUD de fuentes/carpetas + suscripción.
- Listado de artículos + estado leído/guardado.
- Frontend lector mínimo (lista + vista de artículo + marcar leído).
- **Salida:** un usuario puede añadir un feed y leerlo.

### Fase 2 — Descubrimiento (completa el MVP)
- Autodetección de feed desde una URL de web (`<link rel=alternate>` + heurística).
- Importar/exportar **OPML**.
- Búsqueda full-text (Postgres).
- i18n pulido EN/ES en frontend.
- **Salida:** MVP usable como Feedly básico.

### Fase 3 — API pública / acceso externo
- API keys con scopes + gestión desde la UI.
- Rate-limiting (Redis) y versionado `/v1`.
- Documentación pública + SDK generado en `API/`.
- **Salida:** contenido accesible por API desde fuera del NAS.

### Fase 4 — PWA / App
- Service worker, instalable, offline básico, sincronización de estado.
- (Opcional) evaluar app nativa (React Native / Flutter) reutilizando la API.

### Fase 5 — IA local (iGPU + NPU con OpenVINO)
- Servicio `ai/` independiente detrás de una interfaz estable.
- Casos: resúmenes, deduplicación semántica, "feeds inteligentes", ranking.
- Embeddings con `pgvector`; modelos vía **OpenVINO** sobre iGPU/NPU.
- Docker: passthrough `/dev/dri` (iGPU) y `/dev/accel` (NPU).
- **Costura desde ahora:** el núcleo no depende de la IA; se comunica por
  una API interna (`/ai/summarize`, `/ai/embed`) que puede estar apagada.

---

## 8. Riesgos y puntos que cuestan

1. **Ingesta robusta**: feeds rotos, redirecciones, charset, fechas raras,
   rate-limits de los orígenes. → Es el trabajo fino del worker.
2. **Estado por usuario a escala**: modelado ya resuelto (sección 2), pero
   vigilar índices y consultas de "no leídos".
3. **UI del lector**: scroll infinito, atajos, marcado al vuelo. Es pulido.
4. **iGPU/NPU en Docker**: el passthrough depende del NAS/drivers; validar
   pronto (aunque la IA sea Fase 5) para no llevarnos sorpresas.

---

## 9. Próximo paso propuesto

Empezar por la **Fase 0** (andamiaje + `docker compose up` funcionando) y,
en cuanto esté verde, la **Fase 1**. Confirmar antes:

- [ ] Nombre/rol de la carpeta `API/` (contrato+SDK vs. gateway).
- [ ] Frontend: ¿SvelteKit (recomendado) o React/Next?
- [ ] ¿Inicializamos git en el repo?
- [ ] Modelo/tarea de IA concreta que más te interese para la Fase 5
      (resúmenes vs. feeds inteligentes vs. dedup) — solo para dimensionar.
