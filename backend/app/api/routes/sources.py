from __future__ import annotations

import uuid

from fastapi import APIRouter, UploadFile

from app.api.errors import not_implemented
from app.schemas.common import OkResponse
from app.schemas.discover import DiscoveredFeed, DiscoverRequest, OpmlImportResult
from app.schemas.source import SubscribeRequest, SubscriptionOut

router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=list[SubscriptionOut])
async def list_sources() -> list[SubscriptionOut]:
    raise not_implemented("sources.list")


@router.post("/sources", response_model=SubscriptionOut)
async def subscribe(body: SubscribeRequest) -> SubscriptionOut:
    raise not_implemented("sources.subscribe")


@router.delete("/sources/{subscription_id}", response_model=OkResponse)
async def unsubscribe(subscription_id: uuid.UUID) -> OkResponse:
    raise not_implemented("sources.unsubscribe")


@router.post("/discover", response_model=list[DiscoveredFeed])
async def discover(body: DiscoverRequest) -> list[DiscoveredFeed]:
    raise not_implemented("discover")


@router.post("/opml/import", response_model=OpmlImportResult)
async def opml_import(file: UploadFile) -> OpmlImportResult:
    raise not_implemented("opml.import")


@router.get("/opml/export")
async def opml_export() -> None:
    raise not_implemented("opml.export")
