"""Embedded media in feed content.

feedparser sanitises entry HTML and drops <iframe> entirely, so YouTube/Vimeo
players vanished without a trace. We let iframes through its sanitiser and
then replace every one of them here, before storing:

- YouTube / Vimeo  -> a plain link carrying `data-embed="youtube:ID"`; the
  reader turns it into a thumbnail card that loads the (privacy-enhanced)
  player only when tapped. API clients just see a link.
- anything else    -> a plain link to the embedded page (never an iframe).

Podcast/video enclosures (audio/*, video/*) that the content doesn't already
play are appended as <audio>/<video> players.
"""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, urlsplit

from feedparser import sanitizer as _fp_sanitizer

# Let <iframe> survive feedparser's sanitiser so we can rewrite it (see above).
# Nothing stored ever contains an iframe: rewrite_iframes() replaces them all.
_fp_sanitizer._HTMLSanitizer.acceptable_elements = set(
    _fp_sanitizer._HTMLSanitizer.acceptable_elements
) | {"iframe"}

_IFRAME_RE = re.compile(r"<iframe\b([^>]*)>.*?</iframe>|<iframe\b([^>]*)/?>", re.I | re.S)
_SRC_RE = re.compile(r'\bsrc\s*=\s*(["\'])(.*?)\1', re.I | re.S)
_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VIMEO_ID = re.compile(r"^\d{4,12}$")


def embed_for(url: str) -> tuple[str, str] | None:
    """(provider, id) for a YouTube/Vimeo player or watch URL, else None."""
    parts = urlsplit(html.unescape(url).strip())
    host = (parts.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    path = parts.path.rstrip("/")
    vid = None
    if host in ("youtube.com", "youtube-nocookie.com"):
        if path.startswith(("/embed/", "/shorts/", "/live/")):
            vid = path.split("/")[2] if len(path.split("/")) > 2 else None
        elif path == "/watch":
            vid = (parse_qs(parts.query).get("v") or [None])[0]
        if vid and _YT_ID.match(vid):
            return "youtube", vid
    elif host == "youtu.be":
        vid = path.lstrip("/")
        if _YT_ID.match(vid):
            return "youtube", vid
    elif host in ("player.vimeo.com", "vimeo.com"):
        vid = path.split("/")[-1]
        if _VIMEO_ID.match(vid):
            return "vimeo", vid
    return None


def _canonical(provider: str, vid: str) -> str:
    return (
        f"https://www.youtube.com/watch?v={vid}"
        if provider == "youtube"
        else f"https://vimeo.com/{vid}"
    )


def rewrite_iframes(content: str | None) -> str | None:
    """Replace every <iframe> with an embed placeholder link or a plain link."""
    if not content or "<iframe" not in content.lower():
        return content

    def repl(m: re.Match) -> str:
        attrs = m.group(1) or m.group(2) or ""
        src_m = _SRC_RE.search(attrs)
        src = src_m.group(2).strip() if src_m else ""
        if src.startswith("//"):
            src = "https:" + src
        emb = embed_for(src) if src else None
        if emb:
            provider, vid = emb
            label = "YouTube" if provider == "youtube" else "Vimeo"
            return (
                f'<p><a href="{_canonical(provider, vid)}" data-embed="{provider}:{vid}">'
                f"▶ {label}</a></p>"
            )
        parts = urlsplit(src)
        if parts.scheme in ("http", "https") and parts.hostname:
            href = html.escape(src, quote=True)
            return f'<p><a href="{href}">↗ {html.escape(parts.hostname)}</a></p>'
        return ""

    return _IFRAME_RE.sub(repl, content)


def append_enclosures(content: str | None, entry: dict) -> str | None:
    """Add players for audio/video enclosures (podcasts) not already in the content."""
    extra = []
    body = content or ""
    for enc in entry.get("enclosures") or []:
        href = str(enc.get("href") or "").strip()
        mtype = str(enc.get("type") or "").lower()
        parts = urlsplit(href)
        if parts.scheme not in ("http", "https") or not parts.hostname or href in body:
            continue
        src = html.escape(href, quote=True)
        if mtype.startswith("audio/"):
            extra.append(f'<p><audio controls preload="none" src="{src}"></audio></p>')
        elif mtype.startswith("video/"):
            extra.append(f'<p><video controls preload="metadata" src="{src}"></video></p>')
        if len(extra) >= 2:
            break
    if not extra:
        return content
    return body + "\n" + "\n".join(extra)
