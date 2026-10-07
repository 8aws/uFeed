"""Feed icons as small PNGs, to embed in emails (inline images show even when
a mail app blocks remote ones, and opening the email doesn't ping each site).

Fetched through the SSRF-guarded client, size-capped, converted to a 32 px PNG
(feeds often use .ico) and remembered for a day in this process.
"""

from __future__ import annotations

import asyncio
import io
import time

import httpx

from app.core.config import settings
from app.core.netguard import BlockedDestination, public_client

MAX_BYTES = 200_000
SIZE = 32
TTL_S = 24 * 3600
_cache: dict[str, tuple[float, bytes | None]] = {}


def _to_png(data: bytes) -> bytes | None:
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format == "ICO":
                # Use the largest size the .ico carries.
                img.size = sorted(img.info.get("sizes") or [img.size])[-1]
            icon = img.convert("RGBA")
            icon.thumbnail((SIZE, SIZE), Image.LANCZOS)
            out = io.BytesIO()
            icon.save(out, "PNG", optimize=True)
            return out.getvalue()
    except Exception:  # noqa: BLE001 - not an image we can read
        return None


async def _fetch(url: str) -> bytes | None:
    headers = {"User-Agent": settings.user_agent, "Accept": "image/*"}
    try:
        async with public_client(timeout=6.0, follow_redirects=True, headers=headers) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    return None
                body = bytearray()
                async for chunk in resp.aiter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        return None
    except (httpx.HTTPError, BlockedDestination, ValueError):
        return None
    return await asyncio.to_thread(_to_png, bytes(body))


async def png(url: str | None) -> bytes | None:
    """The icon at `url` as a small PNG, or None."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < TTL_S:
        return hit[1]
    data = await _fetch(url)
    _cache[url] = (time.time(), data)
    if len(_cache) > 1000:  # keep it small
        for k in sorted(_cache, key=lambda k: _cache[k][0])[:200]:
            _cache.pop(k, None)
    return data


async def many(urls: list[str | None]) -> dict[str, bytes]:
    """Icons for several URLs at once (missing ones left out)."""
    unique = [u for u in dict.fromkeys(urls) if u]
    found = await asyncio.gather(*(png(u) for u in unique))
    return {u: data for u, data in zip(unique, found, strict=True) if data}
