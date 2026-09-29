"""Playback of cached server-voice audio via signed URLs (see services/tts)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse, StreamingResponse

from app.api.errors import AppError
from app.services import tts

router = APIRouter(prefix="/audio", tags=["audio"])


@router.get("/{name}", response_model=None)
async def play(name: str, exp: int, sig: str) -> FileResponse | StreamingResponse:
    """Serve an article's MP3: the finished file (with Range support, which iOS
    needs to seek), or -- while it's still being generated -- a live stream
    that follows the file as it grows."""
    if not tts.verify(name, exp, sig):
        raise AppError(403, "forbidden", "Invalid or expired audio link.")
    path = tts.cache_path(name)
    if path.exists():
        return FileResponse(
            path, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=21600"}
        )
    if tts.in_progress(name):
        return StreamingResponse(
            tts.follow_live(name), media_type="audio/mpeg", headers={"Cache-Control": "no-store"}
        )
    raise AppError(404, "not_found", "Audio no longer cached; request it again.")
