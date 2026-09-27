from __future__ import annotations

import io

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.core import netguard
from app.core.config import settings
from app.services.ingest import http_url, parse_feed
from tests.test_admin import _h, _register

BLOCKED = [
    "http://127.0.0.1/feed",
    "http://localhost:8000/feed",
    "http://10.0.0.1/rss",
    "http://192.168.100.100:8080/",
    "http://172.17.0.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
    "http://[::ffff:127.0.0.1]/",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "gopher://example.com/",
]


@pytest.mark.parametrize("url", BLOCKED)
async def test_ssrf_guard_blocks_internal(url: str) -> None:
    with pytest.raises(ValueError):
        await netguard.check_destination(url)


async def test_ssrf_guard_allows_public_and_override(monkeypatch) -> None:
    await netguard.check_destination("http://93.184.215.14/feed")  # public literal
    monkeypatch.setattr(settings, "allow_private_feeds", True)
    await netguard.check_destination("http://192.168.1.10/feed")


async def test_ssrf_guard_checks_every_redirect_hop() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "93.184.215.14":
            return httpx.Response(302, headers={"Location": "http://127.0.0.1:6379/"})
        return httpx.Response(200, text="internal!")

    async with netguard.public_client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.RequestError):
            await client.get("http://93.184.215.14/feed", follow_redirects=True)
        with pytest.raises(netguard.BlockedDestination):
            await client.get("http://10.1.2.3/feed")


def test_http_url_keeps_only_http() -> None:
    assert http_url("javascript:alert(1)") is None
    assert http_url(" JavaScript:alert(1)") is None
    assert http_url("data:text/html,<script>") is None
    assert http_url("/img/a.png", "https://site.test/post/1") == "https://site.test/img/a.png"
    assert http_url("https://ok.test/x") == "https://ok.test/x"


def test_parse_feed_drops_script_links() -> None:
    xml = b"""<rss><channel><title>t</title><link>javascript:alert(1)</link>
    <item><title>a</title><link>javascript:alert(document.cookie)</link>
    <description><![CDATA[<p onclick="x()">hi</p><script>alert(1)</script>]]></description>
    </item></channel></rss>"""
    feed = parse_feed(xml)
    assert feed.site_url is None
    art = feed.articles[0]
    assert art.url is None
    assert "<script" not in (art.summary or "") and "onclick" not in (art.summary or "")


async def test_subscribe_rejects_non_http_urls(api: AsyncClient) -> None:
    h = _h(await _register(api))
    for bad in ("javascript:alert(1)", "file:///etc/passwd", "ftp://x.test/f"):
        r = await api.post("/api/sources", headers=h, json={"url": bad})
        assert r.status_code == 422, bad


async def test_opml_limits(api: AsyncClient) -> None:
    h = _h(await _register(api))
    big = io.BytesIO(b"<opml>" + b" " * (2 * 1024 * 1024 + 10) + b"</opml>")
    r = await api.post("/api/opml/import", headers=h, files={"file": ("a.opml", big)})
    assert r.status_code == 413
    evil = b"""<opml version="2.0"><body>
      <outline text="x" xmlUrl="javascript:alert(1)"/>
      <outline text="y" xmlUrl="file:///etc/passwd"/></body></opml>"""
    r = await api.post("/api/opml/import", headers=h, files={"file": ("e.opml", evil)})
    assert r.json() == {"imported": 0, "skipped": 2}


def test_docs_hidden_in_production(monkeypatch) -> None:
    from app.main import create_app

    monkeypatch.setattr(settings, "env", "prod")
    client = TestClient(create_app())
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404, path
    assert client.get("/health").status_code == 200
