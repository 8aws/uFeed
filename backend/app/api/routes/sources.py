from __future__ import annotations

import uuid

from fastapi import APIRouter, UploadFile

from app.api.deps import CurrentUser, DbSession
from app.api.errors import AppError, not_implemented
from app.schemas.common import OkResponse
from app.schemas.discover import DiscoveredFeed, DiscoverRequest, OpmlImportResult
from app.schemas.source import SourceOut, SubscribeRequest, SubscriptionOut
from app.services import folders as folder_service
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
    return _to_out(row)


@router.delete("/sources/{subscription_id}", response_model=OkResponse)
async def unsubscribe(subscription_id: uuid.UUID, user: CurrentUser, db: DbSession) -> OkResponse:
    if not await sub_service.unsubscribe(db, user.id, subscription_id):
        raise AppError(404, "not_found", "Subscription not found.")
    return OkResponse()


# --- WS4: discovery + OPML (still stubbed) ----------------------------------


@router.post("/discover", response_model=list[DiscoveredFeed])
async def discover(body: DiscoverRequest) -> list[DiscoveredFeed]:
    raise not_implemented("discover")


@router.post("/opml/import", response_model=OpmlImportResult)
async def opml_import(file: UploadFile) -> OpmlImportResult:
    raise not_implemented("opml.import")


@router.get("/opml/export")
async def opml_export() -> None:
    raise not_implemented("opml.export")
