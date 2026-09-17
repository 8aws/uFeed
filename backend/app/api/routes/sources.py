from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, UploadFile
from fastapi.responses import Response

from app.api.deps import CurrentUser, DbSession
from app.api.errors import AppError
from app.schemas.common import OkResponse
from app.schemas.discover import DiscoveredFeed, DiscoverRequest, OpmlImportResult
from app.schemas.source import SourceOut, SubscribeRequest, SubscriptionOut
from app.services import discovery as discovery_service
from app.services import folders as folder_service
from app.services import ingest as ingest_service
from app.services import opml as opml_service
from app.services import subscriptions as sub_service
from app.services.subscriptions import SubscriptionRow

router = APIRouter(tags=["sources"])


def _to_out(row: SubscriptionRow) -> SubscriptionOut:
    return SubscriptionOut(
        id=row.subscription.id,
        source=SourceOut.model_validate(row.source),
        folder_id=row.subscription.folder_id,
        custom_title=row.subscription.custom_title,
        unread_count=row.unread_count,
    )


@router.get("/sources", response_model=list[SubscriptionOut])
async def list_sources(user: CurrentUser, db: DbSession) -> list[SubscriptionOut]:
    rows = await sub_service.list_subscriptions(db, user.id)
    return [_to_out(r) for r in rows]


@router.post("/sources", response_model=SubscriptionOut, status_code=201)
async def subscribe(body: SubscribeRequest, user: CurrentUser, db: DbSession) -> SubscriptionOut:
    if body.folder_id is not None:
        if await folder_service.get_folder(db, user.id, body.folder_id) is None:
            raise AppError(404, "not_found", "Folder not found.")
    sub, _created = await sub_service.subscribe(db, user.id, body.url, body.folder_id)
    row = await sub_service.get_subscription_row(db, user.id, sub.id)
    assert row is not None
    # First-time feed: fetch now so the user sees articles immediately instead
    # of waiting for the next worker tick. Best-effort; the worker retries.
    if row.source.last_fetch_at is None:
        try:
            async with httpx.AsyncClient() as client:
                await ingest_service.refresh_source(db, client, row.source)
            row = await sub_service.get_subscription_row(db, user.id, sub.id)
            assert row is not None
        except Exception:  # noqa: BLE001 - never fail a subscribe on a bad feed
            pass
    return _to_out(row)


@router.delete("/sources/{subscription_id}", response_model=OkResponse)
async def unsubscribe(subscription_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    if not await sub_service.unsubscribe(db, user.id, subscription_id):
        raise AppError(404, "not_found", "Subscription not found.")
    return OkResponse()


# --- Discovery + OPML --------------------------------------------------------


@router.post("/discover", response_model=list[DiscoveredFeed])
async def discover(body: DiscoverRequest, user: CurrentUser) -> list[DiscoveredFeed]:
    async with httpx.AsyncClient() as client:
        return await discovery_service.discover_feeds(client, body.url)


@router.post("/opml/import", response_model=OpmlImportResult)
async def opml_import(user: CurrentUser, db: DbSession, file: UploadFile) -> OpmlImportResult:
    content = await file.read()
    imported, skipped = await opml_service.import_opml(db, user.id, content)
    return OpmlImportResult(imported=imported, skipped=skipped)


@router.get("/opml/export")
async def opml_export(user: CurrentUser, db: DbSession) -> Response:
    xml = await opml_service.export_opml(db, user.id)
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Content-Disposition": 'attachment; filename="ufeed.opml"'},
    )
