from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from time import struct_time
from urllib.parse import urljoin, urlsplit

import feedparser
import httpx
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.netguard import public_client
from app.core.text import plain
from app.db.session import SessionLocal
from app.models.article import Article
from app.models.source import Source
from app.services import media
from app.services import retention as retention_service
from app.services import site as site_service


@dataclass(slots=True)
class ParsedArticle:
    guid: str
    url: str | None
    title: str | None
    author: str | None
    content_html: str | None
    summary: str | None
    lang: str | None
    published_at: datetime | None
    image_url: str | None = None
    word_count: int | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParsedFeed:
    title: str | None
    site_url: str | None
    lang: str | None
    articles: list[ParsedArticle]
    favicon_url: str | None = None


@dataclass(slots=True)
class FetchResult:
    status: str  # "ok" | "not_modified" | "error"
    content: bytes | None = None
    etag: str | None = None
    last_modified: str | None = None
    error: str | None = None
    new_articles: int = 0


# --- Parsing -----------------------------------------------------------------


def _struct_to_dt(st: struct_time | None) -> datetime | None:
    if st is None:
        return None
    # feedparser normalises parsed dates to UTC.
    return datetime(*st[:6], tzinfo=UTC)


def _entry_guid(entry: dict) -> str:
    for key in ("id", "guid", "link"):
        value = entry.get(key)
        if value:
            return str(value)
    basis = f"{entry.get('title', '')}|{entry.get('summary', '')}"
    return "sha1:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()


def _entry_content_html(entry: dict) -> str | None:
    content = entry.get("content")
    if content and isinstance(content, list) and content[0].get("value"):
        html_ = content[0]["value"]
    else:
        html_ = entry.get("summary")
    return media.append_enclosures(media.rewrite_iframes(html_), entry)


_TAG_RE = re.compile(r"<[^>]+>")
_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _entry_image(entry: dict, content_html: str | None) -> str | None:
    for mc in entry.get("media_content") or []:
        if isinstance(mc, dict) and mc.get("url"):
            return mc["url"]
    for thumb in entry.get("media_thumbnail") or []:
        if isinstance(thumb, dict) and thumb.get("url"):
            return thumb["url"]
    for link in entry.get("links") or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith("image"):
            if link.get("href"):
                return link["href"]
    if content_html:
        m = _IMG_RE.search(content_html)
        if m:
            return m.group(1)
    return None


def _word_count(html: str | None) -> int | None:
    if not html:
        return None
    text = _TAG_RE.sub(" ", html)
    words = [w for w in re.split(r"\s+", text) if w]
    return len(words) or None


def _entry_tags(entry: dict) -> list[str]:
    tags = entry.get("tags") or []
    out: list[str] = []
    for tag in tags:
        term = (tag.get("term") or tag.get("label") or "").strip() if isinstance(tag, dict) else ""
        if term and term not in out:
            out.append(term)
    return out[:10]


def http_url(url: str | None, base: str | None = None) -> str | None:
    """Keep only absolute http(s) URLs (resolving relative ones against `base`).

    Feed-supplied links end up in href/src attributes; a `javascript:` link
    would run in the reader when clicked, so anything else is dropped.
    """
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if base and not urlsplit(url).scheme:
        url = urljoin(base, url)
    parts = urlsplit(url)
    return url if parts.scheme in ("http", "https") and parts.netloc else None


def _feed_favicon(feed: dict, site_url: str | None) -> str | None:
    image = feed.get("image")
    if isinstance(image, dict) and http_url(image.get("href"), site_url):
        return http_url(image.get("href"), site_url)
    if site_url:
        parts = urlsplit(site_url)
        if parts.scheme and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}/favicon.ico"
    return None


def parse_feed(
    content: bytes, feed_lang_fallback: str | None = None, base_url: str | None = None
) -> ParsedFeed:
    """Parse raw feed bytes into a normalised ParsedFeed (no network).
    `base_url` (the feed's address) resolves relative links and media paths
    such as `/storage/clip.mp4`, which would otherwise point at uFeed itself."""
    headers = {"content-location": base_url} if base_url else None
    parsed = feedparser.parse(content, response_headers=headers)
    feed = parsed.get("feed", {})
    feed_lang = feed.get("language") or feed_lang_fallback

    articles: list[ParsedArticle] = []
    for entry in parsed.get("entries", []):
        published = _struct_to_dt(entry.get("published_parsed") or entry.get("updated_parsed"))
        content_html = _entry_content_html(entry)
        link = http_url(entry.get("link"))
        articles.append(
            ParsedArticle(
                guid=_entry_guid(entry),
                url=link,
                title=plain(entry.get("title")),
                author=plain(entry.get("author")),
                content_html=content_html,
                summary=media.rewrite_iframes(entry.get("summary")),
                lang=entry.get("language") or feed_lang,
                published_at=published,
                image_url=http_url(_entry_image(entry, content_html), link),
                word_count=_word_count(content_html),
                tags=_entry_tags(entry),
            )
        )
    site_url = http_url(feed.get("link"))
    return ParsedFeed(
        title=plain(feed.get("title")),
        site_url=site_url,
        lang=feed_lang,
        articles=articles,
        favicon_url=_feed_favicon(feed, site_url),
    )


# --- Fetching (conditional GET) ---------------------------------------------


async def fetch_feed(client: httpx.AsyncClient, source: Source) -> FetchResult:
    headers = {"User-Agent": settings.user_agent, "Accept": "application/rss+xml, */*"}
    if source.etag:
        headers["If-None-Match"] = source.etag
    if source.last_modified:
        headers["If-Modified-Since"] = source.last_modified
    try:
        resp = await client.get(
            source.feed_url,
            headers=headers,
            follow_redirects=True,
            timeout=settings.http_timeout_s,
        )
    except httpx.HTTPError as exc:
        return FetchResult(status="error", error=f"request: {exc!s}")

    if resp.status_code == 304:
        return FetchResult(status="not_modified")
    if resp.status_code >= 400:
        return FetchResult(status="error", error=f"http {resp.status_code}")
    return FetchResult(
        status="ok",
        content=resp.content,
        etag=resp.headers.get("ETag"),
        last_modified=resp.headers.get("Last-Modified"),
    )


# --- Persistence -------------------------------------------------------------


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


async def store_articles(db: AsyncSession, source: Source, parsed: ParsedFeed) -> int:
    """Insert new articles, skipping duplicates by (source_id, guid).

    Returns the number of newly inserted rows.
    """
    if not parsed.articles:
        return 0

    incoming = {a.guid: a for a in parsed.articles}  # de-dup within the feed itself
    existing = await db.execute(
        select(Article.guid).where(Article.source_id == source.id, Article.guid.in_(list(incoming)))
    )
    known = set(existing.scalars().all())
    new = [a for guid, a in incoming.items() if guid not in known]
    # Don't (re-)ingest what the next retention purge would delete: dated entries
    # older than the window that also fall outside the feed's newest
    # KEEP_PER_SOURCE. Otherwise purged items still listed by a large feed would
    # come back as "new"; small or slow feeds are still ingested in full.
    days = int((await site_service.get_settings(db))["retention_days"])
    cutoff = retention_service.cutoff_for(days)
    if cutoff is not None and new:
        dated = [_aware(a.published_at) for a in new if a.published_at is not None]
        horizon = await retention_service.keep_horizon(db, source.id, dated)
        if horizon is not None:
            limit = min(cutoff, horizon)
            new = [a for a in new if a.published_at is None or _aware(a.published_at) >= limit]
    if not new:
        return 0

    rows = [
        {
            "source_id": source.id,
            "guid": a.guid,
            "url": a.url,
            "title": a.title,
            "author": a.author,
            "content_html": a.content_html,
            "summary": a.summary,
            "image_url": a.image_url,
            "lang": a.lang,
            "word_count": a.word_count,
            "tags": a.tags,
            "published_at": a.published_at,
        }
        for a in new
    ]
    # ON CONFLICT DO NOTHING guards against races with a second worker.
    stmt = (
        pg_insert(Article).values(rows).on_conflict_do_nothing(constraint="uq_articles_source_guid")
    )
    result = await db.execute(stmt)
    return result.rowcount or 0


# --- og:image fallback -------------------------------------------------------

_OG_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\']'
    r'[^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_RE_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\']'
    r'[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\']',
    re.IGNORECASE,
)


async def fetch_og_image(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(
            url,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
            timeout=settings.http_timeout_s,
        )
        if resp.status_code >= 400:
            return None
        html = resp.text[:200_000]
    except httpx.HTTPError:
        return None
    for rx in (_OG_RE, _OG_RE_REV):
        m = rx.search(html)
        if m:
            return http_url(m.group(1), url)
    return None


async def backfill_images(db: AsyncSession, client: httpx.AsyncClient, source: Source) -> int:
    """Recover og:image for freshly ingested articles that lack one."""
    if settings.og_image_max_per_source <= 0:
        return 0
    cutoff = datetime.now(UTC) - timedelta(minutes=10)
    rows = (
        await db.execute(
            select(Article.id, Article.url)
            .where(
                Article.source_id == source.id,
                Article.image_url.is_(None),
                Article.url.isnot(None),
                Article.fetched_at >= cutoff,
            )
            .limit(settings.og_image_max_per_source)
        )
    ).all()
    found = 0
    for aid, url in rows:
        og = await fetch_og_image(client, url)
        if og:
            await db.execute(update(Article).where(Article.id == aid).values(image_url=og))
            found += 1
    if found:
        await db.commit()
    return found


# --- Scheduling / backoff ----------------------------------------------------


def compute_next_fetch(
    interval_s: int, error_count: int, *, now: datetime | None = None
) -> datetime:
    """Next poll time. Exponential backoff while error_count > 0, capped."""
    now = now or datetime.now(UTC)
    if error_count <= 0:
        delay = interval_s
    else:
        delay = min(interval_s * (2**error_count), settings.ingest_max_interval_s)
    return now + timedelta(seconds=delay)


async def refresh_source(
    db: AsyncSession, client: httpx.AsyncClient, source: Source
) -> FetchResult:
    """Fetch, parse, store, and reschedule a single source."""
    result = await fetch_feed(client, source)
    now = datetime.now(UTC)

    if result.status == "error":
        source.error_count += 1
        source.last_error = (result.error or "fetch failed")[:500]
        source.last_error_at = now
        source.next_fetch_at = compute_next_fetch(
            source.fetch_interval_s, source.error_count, now=now
        )
        await db.commit()
        return result

    if result.status == "ok" and result.content is not None:
        parsed = parse_feed(result.content, base_url=source.feed_url)
        result.new_articles = await store_articles(db, source, parsed)
        await backfill_images(db, client, source)
        if not source.title and parsed.title:
            source.title = parsed.title
        if not source.site_url and parsed.site_url:
            source.site_url = parsed.site_url
        if not source.favicon_url and parsed.favicon_url:
            source.favicon_url = parsed.favicon_url
        source.etag = result.etag
        source.last_modified = result.last_modified

    # Success (ok or not_modified): clear errors and schedule normally.
    source.error_count = 0
    source.last_error = None
    source.last_fetch_at = now
    source.next_fetch_at = compute_next_fetch(source.fetch_interval_s, 0, now=now)
    await db.commit()
    return result


@dataclass(slots=True)
class RefreshSummary:
    checked: int = 0
    new_articles: int = 0
    errors: int = 0


async def refresh_sources(source_ids: list[uuid.UUID], concurrency: int = 6) -> RefreshSummary:
    """On-demand refresh of several sources concurrently (each in its own
    session). Used by the manual "refresh" button."""
    summary = RefreshSummary()
    if not source_ids:
        return summary
    sem = asyncio.Semaphore(concurrency)

    async with public_client() as client:

        async def one(sid: uuid.UUID) -> None:
            async with sem, SessionLocal() as session:
                src = await session.get(Source, sid)
                if src is None:
                    return
                try:
                    result = await refresh_source(session, client, src)
                except Exception:  # noqa: BLE001 - a bad feed shouldn't fail the batch
                    summary.errors += 1
                    return
                summary.checked += 1
                if result.status == "error":
                    summary.errors += 1
                else:
                    summary.new_articles += result.new_articles

        await asyncio.gather(*(one(sid) for sid in source_ids))
    return summary
