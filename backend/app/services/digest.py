"""Daily digest: the most relevant unread articles of the last day from your
feeds, by email at the hour you choose (Settings) and as an API (also with an
API key, e.g. for a daily-summary app).

Relevance, kept simple and explainable: how many people read it in the last
two days, how many feeds carried the same story (near-duplicates), and how
fresh it is; at most three per feed so one busy site doesn't fill it.
"""

from __future__ import annotations

import html
import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_digest_off_token
from app.core.text import plain, text_of
from app.db.session import SessionLocal
from app.models.article_ai import ArticleAI
from app.models.read_event import ReadEvent
from app.models.source import Source
from app.models.user import User
from app.services import articles as article_service
from app.services import favicons, mailer

log = logging.getLogger("ufeed.digest")

PER_SOURCE = 3
EXCERPT = 260


def _ts(a) -> datetime:
    return a.published_at or a.fetched_at or datetime.now(UTC)


async def build(db: AsyncSession, user: User, hours: int = 24, limit: int = 8) -> dict[str, Any]:
    """The digest for this user: {hours, total_new, items: [...]}."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    page = await article_service.list_articles(db, user.id, unread=True, limit=200)
    fresh = [r for r in page.rows if _ts(r.article) >= since]
    if not fresh:
        return {"hours": hours, "total_new": 0, "items": []}
    ids = [r.article.id for r in fresh]
    readers = dict(
        (
            await db.execute(
                select(ReadEvent.article_id, func.count(func.distinct(ReadEvent.user_id)))
                .where(
                    ReadEvent.article_id.in_(ids),
                    ReadEvent.created_at >= datetime.now(UTC) - timedelta(hours=48),
                )
                .group_by(ReadEvent.article_id)
            )
        ).all()
    )
    now = datetime.now(UTC)

    def score(r) -> float:
        age_h = (now - _ts(r.article)).total_seconds() / 3600
        return 3 * readers.get(r.article.id, 0) + 2 * (r.dup_count - 1) + max(0, 1 - age_h / hours)

    picked, per_source = [], {}
    for r in sorted(fresh, key=score, reverse=True):
        sid = r.article.source_id
        if per_source.get(sid, 0) >= PER_SOURCE:
            continue
        per_source[sid] = per_source.get(sid, 0) + 1
        picked.append(r)
        if len(picked) >= limit:
            break

    lang = (user.locale or "en")[:2]
    summaries = dict(
        (
            await db.execute(
                select(ArticleAI.article_id, ArticleAI.summary).where(
                    ArticleAI.article_id.in_([r.article.id for r in picked]), ArticleAI.lang == lang
                )
            )
        ).all()
    )
    feeds = {
        sid: (title, icon)
        for sid, title, icon in (
            await db.execute(
                select(Source.id, Source.title, Source.favicon_url).where(
                    Source.id.in_({r.article.source_id for r in picked})
                )
            )
        ).all()
    }
    items = []
    for r in picked:
        a = r.article
        text = summaries.get(a.id)
        if not text:
            body = text_of(a.summary or a.content_html)
            text = body[:EXCERPT].rsplit(" ", 1)[0] + "…" if len(body) > EXCERPT else body
        items.append(
            {
                "id": str(a.id),
                "title": plain(a.title or "") or "",
                "source": feeds.get(a.source_id, ("", None))[0] or "",
                "icon_url": feeds.get(a.source_id, ("", None))[1],
                "url": a.url,
                "published_at": _ts(a).isoformat(),
                "summary": text,
                "ai_summary": a.id in summaries,
                "readers": readers.get(a.id, 0),
            }
        )
    return {"hours": hours, "total_new": len(fresh), "items": items}


TEXT = {
    "es": {
        "subject": "Tu resumen de uFeed: {n} artículos destacados",
        "title": "Tu resumen diario",
        "intro": (
            "Lo más relevante de las últimas 24 horas en tus fuentes · {total} nuevos sin leer"
        ),
        "open": "Leer en uFeed",
        "source": "Original",
        "ai": "Resumen IA",
        "ago_h": "hace {n} h",
        "ago_m": "hace {n} min",
        "ago_d": "hace {n} d",
        "off": "Desactivar este resumen",
        "settings": "Ajustes",
        "why": "Recibes este correo porque activaste el resumen diario en uFeed.",
        "days": ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"],
        "months": [
            "enero",
            "febrero",
            "marzo",
            "abril",
            "mayo",
            "junio",
            "julio",
            "agosto",
            "septiembre",
            "octubre",
            "noviembre",
            "diciembre",
        ],
        "date": "{day} {d} de {month}",
    },
    "en": {
        "subject": "Your uFeed digest: {n} top articles",
        "title": "Your daily digest",
        "intro": "The most relevant of the last 24 hours in your feeds · {total} new unread",
        "open": "Read in uFeed",
        "source": "Original",
        "ai": "AI summary",
        "ago_h": "{n} h ago",
        "ago_m": "{n} min ago",
        "ago_d": "{n} d ago",
        "off": "Turn off this digest",
        "settings": "Settings",
        "why": "You get this email because you turned on the daily digest in uFeed.",
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "months": [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        "date": "{day}, {month} {d}",
    },
}

LOGO = Path(__file__).resolve().parent.parent / "assets" / "logo-96.png"
ACCENT = "#2563eb"
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def _ago(t: dict[str, Any], iso: str) -> str:
    try:
        mins = int((datetime.now(UTC) - datetime.fromisoformat(iso)).total_seconds() // 60)
    except ValueError:
        return ""
    if mins < 60:
        return t["ago_m"].format(n=max(1, mins))
    if mins < 48 * 60:
        return t["ago_h"].format(n=mins // 60)
    return t["ago_d"].format(n=mins // (24 * 60))


def render(
    user: User, digest: dict[str, Any], icons: dict[str, bytes] | None = None
) -> tuple[str, str, str, str, dict[str, bytes]]:
    """(subject, text, html, one-click unsubscribe URL, inline images) for the
    email. `icons` maps feed icon URLs to small PNGs (from favicons.many)."""
    t = TEXT.get((user.locale or "en")[:2], TEXT["en"])
    base = settings.public_url.rstrip("/")
    off = f"{base}/api/digest/off?token={create_digest_off_token(str(user.id))}"
    items = digest["items"]
    subject = t["subject"].format(n=len(items))
    intro = t["intro"].format(total=digest["total_new"])
    now = _local_now()
    today = t["date"].format(
        day=t["days"][now.weekday()], d=now.day, month=t["months"][now.month - 1]
    )

    # Plain-text version.
    lines = [f"uFeed · {t['title']} · {today}", intro, ""]
    for i, it in enumerate(items, 1):
        lines += [
            f"{i}. {it['title']}",
            f"   {it['source']} · {_ago(t, it['published_at'])}",
            f"   {it['summary']}",
            f"   {base}/?a={it['id']}",
            "",
        ]
    lines += [t["why"], f"{t['off']}: {off}"]

    # Inline images: the app logo and one icon per feed.
    images: dict[str, bytes] = {}
    if LOGO.exists():
        images["logo@ufeed"] = LOGO.read_bytes()
    cids: dict[str, str] = {}
    for url, data in (icons or {}).items():
        cids[url] = f"feed{len(cids)}@ufeed"
        images[cids[url]] = data

    e = html.escape
    logo = (
        '<img src="cid:logo@ufeed" width="40" height="40" alt="uFeed" '
        'style="display:block;border:0;border-radius:10px">'
        if "logo@ufeed" in images
        else ""
    )
    cards = []
    for i, it in enumerate(items):
        link = f"{base}/?a={it['id']}"
        icon_cid = cids.get(it.get("icon_url") or "")
        icon = (
            f'<img src="cid:{icon_cid}" width="16" height="16" alt="" '
            f'style="vertical-align:-3px;border:0;border-radius:3px;margin-right:6px">'
            if icon_cid
            # No icon: the feed's initial in a small circle keeps the line tidy.
            else f'<span style="display:inline-block;width:16px;height:16px;line-height:16px;'
            f"border-radius:50%;background:#e0e7ff;color:{ACCENT};font-size:10px;"
            f'font-weight:700;text-align:center;margin-right:6px">'
            f"{e((it['source'] or '?')[:1].upper())}</span>"
        )
        badge = (
            f'<span style="display:inline-block;margin-left:6px;padding:1px 7px;'
            f'border-radius:999px;background:#eef2ff;color:{ACCENT};font-size:11px">'
            f'✨ {e(t["ai"])}</span>'
            if it.get("ai_summary")
            else ""
        )
        original = (
            f'<a href="{e(it["url"])}" style="color:#6b7280;font-size:13px;'
            f'text-decoration:none;margin-left:14px">{e(t["source"])} ↗</a>'
            if it.get("url")
            else ""
        )
        cards.append(
            f'<tr><td style="padding:0 0 14px">'
            f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
            f'style="background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;'
            f'border-left:4px solid {ACCENT if i == 0 else "#c7d2fe"}">'
            f'<tr><td style="padding:16px 18px">'
            f'<div style="font-size:12px;color:#6b7280;letter-spacing:.02em">{icon}'
            f'<strong style="color:#374151;text-transform:uppercase">{e(it["source"])}</strong>'
            f' · {e(_ago(t, it["published_at"]))}{badge}</div>'
            f'<a href="{e(link)}" style="display:block;margin:8px 0 6px;font-size:18px;'
            f'line-height:1.3;font-weight:700;color:#111827;text-decoration:none">'
            f'{e(it["title"])}</a>'
            f'<div style="font-size:14px;line-height:1.55;color:#374151">{e(it["summary"])}</div>'
            f'<div style="margin-top:12px"><a href="{e(link)}" style="display:inline-block;'
            f"padding:7px 14px;border-radius:999px;background:{ACCENT};color:#ffffff;"
            f'font-size:13px;font-weight:600;text-decoration:none">{e(t["open"])} →</a>'
            f"{original}</div>"
            f"</td></tr></table></td></tr>"
        )
    page = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light"><meta name="supported-color-schemes" '
        'content="light"></head>'
        f'<body style="margin:0;padding:0;background:#f3f4f6;font-family:{FONT}">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="background:#f3f4f6"><tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
        'style="max-width:600px">'
        # Header: logo, name, date.
        '<tr><td style="padding:0 4px 18px"><table role="presentation" cellspacing="0" '
        f'cellpadding="0"><tr><td style="padding-right:12px">{logo}</td><td>'
        '<div style="font-size:20px;font-weight:800;color:#111827">uFeed</div>'
        f'<div style="font-size:13px;color:#6b7280">{e(t["title"])} · {e(today)}</div>'
        "</td></tr></table></td></tr>"
        f'<tr><td style="padding:0 4px 16px;font-size:14px;color:#4b5563">{e(intro)}</td></tr>'
        + "".join(cards)
        + '<tr><td style="padding:10px 4px 0;font-size:12px;line-height:1.5;color:#9ca3af">'
        f'{e(t["why"])}<br><a href="{e(off)}" style="color:#6b7280">{e(t["off"])}</a> · '
        f'<a href="{e(base)}/settings" style="color:#6b7280">{e(t["settings"])}</a>'
        "</td></tr></table></td></tr></table></body></html>"
    )
    return subject, "\n".join(lines), page, off, images


def on_day(user: User, day: date) -> bool:
    """Whether the digest goes out on that day (Monday = bit 0)."""
    return bool((user.digest_days or 127) >> day.weekday() & 1)


def _local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.digest_tz))


async def send_one(db: AsyncSession, user: User, today: date) -> bool:
    digest = await build(db, user)
    sent = False
    if digest["items"]:
        icons = await favicons.many([it.get("icon_url") for it in digest["items"]])
        subject, text, page, off, images = render(user, digest, icons)
        sent = await mailer.send(
            user.email,
            subject,
            text,
            page,
            headers={
                "List-Unsubscribe": f"<{off}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
            images=images,
        )
    # Mark the day either way (nothing new is not worth a retry every hour);
    # a failed send is retried next hour.
    if sent or not digest["items"]:
        await db.execute(update(User).where(User.id == user.id).values(digest_sent_on=today))
        await db.commit()
    return sent


async def run_due() -> int:
    """Hourly (worker): send the digest to everyone whose hour has come and
    who hasn't had today's. Returns how many were sent."""
    if not mailer.enabled():
        return 0
    now = _local_now()
    today = now.date()
    sent = 0
    async with SessionLocal() as db:
        users = (
            await db.execute(
                select(User).where(
                    User.is_active.is_(True),
                    User.digest_hour.is_not(None),
                    User.digest_hour <= now.hour,
                    (User.digest_sent_on.is_(None)) | (User.digest_sent_on < today),
                )
            )
        ).scalars()
        for user in list(users):
            if not on_day(user, today):
                continue  # not one of its days (e.g. weekdays only)
            try:
                sent += int(await send_one(db, user, today))
            except Exception:  # noqa: BLE001 - one user's problem doesn't stop the rest
                log.exception("digest for %s failed", user.id)
        # An hour ahead: queue AI summaries (low priority) for the next round
        # of digests, so the email shows summaries rather than excerpts.
        ahead = now + timedelta(hours=1)
        soon = ahead.hour
        upcoming = (
            await db.execute(
                select(User).where(
                    User.is_active.is_(True),
                    User.digest_hour == soon,
                    (User.digest_sent_on.is_(None)) | (User.digest_sent_on < today),
                )
            )
        ).scalars()
        for user in list(upcoming):
            if not on_day(user, ahead.date()):
                continue
            try:
                await prepare(db, user)
            except Exception:  # noqa: BLE001 - only a head start
                log.exception("digest summaries for %s failed", user.id)
    if sent:
        log.info("sent %d digests", sent)
    return sent


async def prepare(db: AsyncSession, user: User) -> int:
    """Queue the missing AI summaries of this user's next digest."""
    from app.services import ai_queue

    lang = (user.locale or "en")[:2]
    queued = 0
    for it in (await build(db, user))["items"]:
        if not it["ai_summary"]:
            _, created = await ai_queue.enqueue(uuid.UUID(it["id"]), lang, ai_queue.BACKGROUND)
            queued += int(created)
    return queued


async def turn_off(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(update(User).where(User.id == user_id).values(digest_hour=None))
    await db.commit()
