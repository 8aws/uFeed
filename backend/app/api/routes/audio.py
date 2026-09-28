"""Playback of cached server-voice audio via signed URLs (see services/tts)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.errors import AppError
from app.services import tts

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/{name}")
async def play(name: str, exp: int, sig: str) -> FileResponse:
    """Serve an article's MP3 (supports Range requests, which iOS needs)."""
    if not tts.verify(name, exp, sig):
        raise AppError(403, "forbidden", "Invalid or expired audio link.")
    path = tts.cache_path(name)
    if not path.exists():
        raise AppError(404, "not_found", "Audio no longer cached; request it again.")
    return FileResponse(
        path, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=21600"}
    )
