from __future__ import annotations

import httpx

from app.services.discovery import discover_feeds

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<title>Blog Feed</title><link>https://blog.example.com</link>
<item><title>Hi</title><link>https://blog.example.com/1</link><guid>1</guid></item>
</channel></rss>"""

HTML_WITH_LINK = b"""<!doctype html><html><head>
<title>My Blog</title>
<link rel="alternate" type="application/rss+xml" href="/feed.xml" title="Blog RSS">
</head><body>hello</body></html>"""

HTML_NO_LINK = b"""<!doctype html><html><head><title>Bare</title></head>
<body>nothing here</body></html>"""


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_discovers_feed_from_html_link() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in ("", "/"):
            return httpx.Response(
                200, content=HTML_WITH_LINK, headers={"content-type": "text/html"}
            )
        return httpx.Response(404)

    async with _client(handler) as client:
        feeds = await discover_feeds(client, "https://blog.example.com/")
    assert len(feeds) == 1
    assert feeds[0].feed_url == "https://blog.example.com/feed.xml"
    assert feeds[0].title == "Blog RSS"


async def test_url_that_is_itself_a_feed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=RSS, headers={"content-type": "application/rss+xml"})

    async with _client(handler) as client:
        feeds = await discover_feeds(client, "https://blog.example.com/feed.xml")
    assert len(feeds) == 1
    assert feeds[0].feed_url == "https://blog.example.com/feed.xml"
    assert feeds[0].title == "Blog Feed"


async def test_common_path_heuristic() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in ("", "/"):
            return httpx.Response(200, content=HTML_NO_LINK, headers={"content-type": "text/html"})
        if request.url.path == "/feed":
            return httpx.Response(200, content=RSS)
        return httpx.Response(404)

    async with _client(handler) as client:
        feeds = await discover_feeds(client, "https://blog.example.com")
    assert [f.feed_url for f in feeds] == ["https://blog.example.com/feed"]


async def test_no_feed_found_returns_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in ("", "/"):
            return httpx.Response(200, content=HTML_NO_LINK, headers={"content-type": "text/html"})
        return httpx.Response(404)

    async with _client(handler) as client:
        feeds = await discover_feeds(client, "https://blog.example.com")
    assert feeds == []
