from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin

import feedparser
import httpx

from app.core.config import settings
from app.schemas.discover import DiscoveredFeed

# Probed when a page exposes no <link rel="alternate"> feeds.
COMMON_PATHS = (
    "/feed",
    "/rss",
    "/rss.xml",
    "/feed.xml",
    "/atom.xml",
    "/index.xml",
    "/feeds/posts/default",
)

_FEED_TYPE_HINTS = ("rss", "atom", "xml")


class _LinkExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.feeds: list[tuple[str, str | None]] = []  # (href, title)
        self.page_title: str | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = {k.lower(): (v or "") for k, v in attrs}
        if tag == "link":
            rel = d.get("rel", "").lower()
            typ = d.get("type", "").lower()
            href = d.get("href")
            if "alternate" in rel and any(h in typ for h in _FEED_TYPE_HINTS) and href:
                self.feeds.append((href, d.get("title") or None))
        elif tag == "title" and self.page_title is None:
            self._in_title = True

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.page_title = data.strip()
            self._in_title = False

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False


async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response | None:
    try:
        resp = await client.get(
            url,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
            timeout=settings.http_timeout_s,
        )
    except httpx.HTTPError:
        return None
    return resp if resp.status_code < 400 else None


def _as_feed_title(content: bytes) -> tuple[bool, str | None]:
    """(is_feed, feed_title)."""
    parsed = feedparser.parse(content)
    if parsed.version:
        return True, parsed.get("feed", {}).get("title")
    return False, None


async def discover_feeds(client: httpx.AsyncClient, url: str) -> list[DiscoveredFeed]:
    """Find feed candidates for a page or feed URL (see A.7 /discover)."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    resp = await _get(client, url)
    if resp is None:
        return []

    # The URL might already be a feed.
    is_feed, title = _as_feed_title(resp.content)
    if is_feed:
        return [DiscoveredFeed(feed_url=str(resp.url), title=title)]

    # Otherwise parse HTML for <link rel="alternate"> feeds.
    base = str(resp.url)
    extractor = _LinkExtractor()
    try:
        extractor.feed(resp.content.decode(resp.encoding or "utf-8", "replace"))
    except Exception:  # noqa: BLE001 - malformed HTML must not crash discovery
        pass

    found: dict[str, str | None] = {}
    for href, link_title in extractor.feeds:
        found.setdefault(urljoin(base, href), link_title or extractor.page_title)

    # Heuristic fallback: probe common feed paths.
    if not found:
        for path in COMMON_PATHS:
            candidate = urljoin(base, path)
            probe = await _get(client, candidate)
            if probe is None:
                continue
            ok, probe_title = _as_feed_title(probe.content)
            if ok:
                found.setdefault(str(probe.url), probe_title or extractor.page_title)

    return [DiscoveredFeed(feed_url=u, title=t) for u, t in found.items()]
