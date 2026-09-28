"""Editor tools: curate what every user shares — the starter catalogue, the
health of the instance's feeds and the shared rankings (Trending/insights).
Open to editors and admins; no access to accounts, plans or backups."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.api.deps import CuratorUser, DbSession
from app.api.errors import AppError
from app.api.routes.articles import _to_out
from app.api.routes.sources import health_out
from app.models.article import Article
from app.models.hidden_article import HiddenArticle
from app.models.source import Source
from app.models.user import User
from app.schemas.common import OkResponse
from app.schemas.curation import Catalog, HiddenArticleOut, HiddenIds, HideRequest
from app.schemas.source import SourceHealthOut, SourcePauseRequest
from app.services import articles as article_service
from app.services import site as site_service
from app.services import source_health

router = APIRouter(prefix="/curation", tags=["curation"])

CATALOG_KEY = "catalog"


async def load_catalog(db: DbSession) -> Catalog:
    saved = await site_service.get_internal(db, CATALOG_KEY)
    return Catalog.model_validate(saved) if saved else Catalog()


# --- Starter catalogue ------------------------------------------------------------


@router.put("/catalog", response_model=Catalog)
async def save_catalog(body: Catalog, _: CuratorUser, db: DbSession) -> Catalog:
    """Replace the starter catalogue (sections=None restores the built-in one)."""
    if body.sections is None:
        value = None
    else:
        value = Catalog(sections=body.sections, updated_at=datetime.now(UTC)).model_dump(
            mode="json"
        )
    await site_service.set_internal(db, CATALOG_KEY, value)
    return await load_catalog(db)


# --- Feed health ----------------------------------------------------------------


@router.get("/sources", response_model=list[SourceHealthOut])
async def curation_sources(_: CuratorUser, db: DbSession) -> list[SourceHealthOut]:
    """Every feed on the instance, problems first, with subscriber counts."""
    return [health_out(r) for r in await source_health.for_admin(db)]


@router.patch("/sources/{source_id}", response_model=OkResponse)
async def pause_source(
    source_id: uuid.UUID, body: SourcePauseRequest, _: CuratorUser, db: DbSession
) -> OkResponse:
    """Pause polling of a dead feed (or resume it, retrying soon)."""
    src = await db.get(Source, source_id)
    if src is None:
        raise AppError(404, "not_found", "Source not found.")
    await source_health.set_paused(db, src, body.paused)
    return OkResponse()


@router.post("/sources/delete-orphans")
async def delete_orphan_sources(_: CuratorUser, db: DbSession) -> dict[str, int]:
    """Remove feeds nobody follows (keeps any with saved/favourite articles)."""
    return {"deleted": await source_health.delete_orphans(db)}


# --- Shared rankings ------------------------------------------------------------


@router.get("/hidden", response_model=list[HiddenArticleOut])
async def hidden_articles(user: CuratorUser, db: DbSession) -> list[HiddenArticleOut]:
    """Articles kept out of Trending and the insight rankings, newest first."""
    rows = (
        await db.execute(
            select(HiddenArticle, User.display_name, User.email)
            .outerjoin(User, User.id == HiddenArticle.hidden_by)
            .order_by(HiddenArticle.created_at.desc())
            .limit(200)
        )
    ).all()
    arts = await article_service.rows_for_ids(db, user.id, [h.article_id for h, _, _ in rows])
    by_id = {r.article.id: r for r in arts}
    return [
        HiddenArticleOut(
            article=_to_out(by_id[h.article_id]),
            hidden_at=h.created_at,
            hidden_by=name or email,
        )
        for h, name, email in rows
        if h.article_id in by_id
    ]


@router.get("/hidden/ids", response_model=HiddenIds)
async def hidden_ids(_: CuratorUser, db: DbSession) -> HiddenIds:
    return HiddenIds(ids=list((await db.execute(select(HiddenArticle.article_id))).scalars()))


@router.put("/articles/{article_id}/hidden", response_model=OkResponse)
async def set_hidden(
    article_id: uuid.UUID, body: HideRequest, user: CuratorUser, db: DbSession
) -> OkResponse:
    """Hide an article from (or restore it to) the shared rankings."""
    if await db.get(Article, article_id) is None:
        raise AppError(404, "not_found", "Article not found.")
    if body.hidden:
        await db.execute(
            pg_insert(HiddenArticle)
            .values(article_id=article_id, hidden_by=user.id)
            .on_conflict_do_nothing()
        )
    else:
        await db.execute(delete(HiddenArticle).where(HiddenArticle.article_id == article_id))
    await db.commit()
    return OkResponse()
