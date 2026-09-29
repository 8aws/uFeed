from __future__ import annotations

from app.services.ingest import parse_feed
from app.services.media import embed_for

FEED = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
<link>https://ex.org/</link><item><title>a</title><link>https://ex.org/p/1</link>
<description><![CDATA[<p>Intro <img src="/img/a.png"> <a href="/b">b</a></p>
<video autoplay muted><source src="/v.mp4" type="video/mp4"></video>
<iframe width="560" src="https://www.youtube-nocookie.com/embed/abcdefghijk?rel=0"></iframe>
<iframe src="//player.vimeo.com/video/123456789"></iframe>
<iframe src="https://open.spotify.com/embed/episode/xyz"></iframe>
<iframe src="javascript:alert(1)"></iframe>]]></description>
<enclosure url="https://ex.org/ep1.mp3" length="123" type="audio/mpeg"/>
<enclosure url="https://ex.org/cover.jpg" length="1" type="image/jpeg"/>
</item></channel></rss>"""


def test_media_is_kept_and_made_safe() -> None:
    art = parse_feed(FEED, base_url="https://ex.org/feed.xml").articles[0]
    html = art.content_html or ""
    # Relative paths resolve against the feed, not against uFeed.
    assert 'src="https://ex.org/img/a.png"' in html
    assert 'href="https://ex.org/b"' in html
    assert 'src="https://ex.org/v.mp4"' in html
    # No iframe is ever stored; known players become embed links.
    assert "<iframe" not in html.lower()
    assert 'data-embed="youtube:abcdefghijk"' in html
    assert 'href="https://www.youtube.com/watch?v=abcdefghijk"' in html
    assert 'data-embed="vimeo:123456789"' in html
    assert 'href="https://open.spotify.com/embed/episode/xyz"' in html
    assert "javascript:" not in html
    # Podcast audio becomes a player; image enclosures don't.
    assert '<audio controls preload="none" src="https://ex.org/ep1.mp3">' in html
    assert "cover.jpg" not in html


def test_embed_for() -> None:
    assert embed_for("https://youtu.be/abcdefghijk") == ("youtube", "abcdefghijk")
    assert embed_for("https://m.youtube.com/watch?v=abcdefghijk&t=3") == ("youtube", "abcdefghijk")
    assert embed_for("https://www.youtube.com/shorts/abcdefghijk") == ("youtube", "abcdefghijk")
    assert embed_for("https://vimeo.com/123456789") == ("vimeo", "123456789")
    assert embed_for("https://www.youtube.com/embed/short") is None
    assert embed_for("https://evil.example/embed/abcdefghijk") is None


def test_titles_are_decoded() -> None:
    from app.core.text import plain

    assert plain("Meta&#8217;s Muse AI sent a YouTuber’s address") == (
        "Meta’s Muse AI sent a YouTuber’s address"
    )
    assert plain("Tom &amp;#8216;Q&amp;A&amp;#8217;") == "Tom ‘Q&A’"
    assert plain("R&D and AT&T") == "R&D and AT&T"
    feed = FEED.replace(b"<title>a</title>", b"<title>Roku&amp;#8217;s TVs</title>")
    art = parse_feed(feed, base_url="https://ex.org/feed.xml").articles[0]
    assert art.title == "Roku’s TVs"
