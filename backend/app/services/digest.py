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
from app.services import mailer

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
    names = dict(
        (
            await db.execute(
                select(Source.id, Source.title).where(
                    Source.id.in_({r.article.source_id for r in picked})
                )
            )
        ).all()
    )
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
                "source": names.get(a.source_id) or "",
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
        "intro": (
            "Lo más relevante de las últimas 24 horas en tus fuentes ({total} nuevos sin leer)."
        ),
        "open": "Abrir en uFeed",
        "source": "Original",
        "off": "¿No quieres recibir este resumen? Desactívalo aquí:",
    },
    "en": {
        "subject": "Your uFeed digest: {n} top articles",
        "intro": "The most relevant of the last 24 hours in your feeds ({total} new unread).",
        "open": "Open in uFeed",
        "source": "Original",
        "off": "Don't want this digest? Turn it off here:",
    },
}


def render(user: User, digest: dict[str, Any]) -> tuple[str, str, str, str]:
    """(subject, text, html, one-click unsubscribe URL) for the email."""
    t = TEXT.get((user.locale or "en")[:2], TEXT["en"])
    base = settings.public_url.rstrip("/")
    off = f"{base}/api/digest/off?token={create_digest_off_token(str(user.id))}"
    items = digest["items"]
    subject = t["subject"].format(n=len(items))
    intro = t["intro"].format(total=digest["total_new"])
    lines = [intro, ""]
    for i, it in enumerate(items, 1):
        lines += [
            f"{i}. {it['title']} — {it['source']}",
            it["summary"],
            f"{base}/?a={it['id']}",
            "",
        ]
    lines += [t["off"], off]
    e = html.escape
    rows = "".join(
        f'<tr><td style="padding:12px 0;border-bottom:1px solid #e5e7eb">'
        f'<div style="font-size:12px;color:#6b7280">{e(it["source"])}</div>'
        f'<a href="{e(base)}/?a={e(it["id"])}" style="font-size:16px;font-weight:600;'
        f'color:#111827;text-decoration:none">{e(it["title"])}</a>'
        f'<div style="font-size:14px;color:#374151;margin-top:4px">{e(it["summary"])}</div>'
        f'<div style="font-size:12px;margin-top:4px"><a href="{e(base)}/?a={e(it["id"])}">'
        f'{e(t["open"])}</a>'
        + (f' · <a href="{e(it["url"])}">{e(t["source"])}</a>' if it.get("url") else "")
        + "</div></td></tr>"
        for it in items
    )
    page = (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:600px;'
        'margin:auto;padding:16px">'
        f'<h2 style="margin:0 0 4px">uFeed</h2><p style="color:#374151">{e(intro)}</p>'
        f'<table width="100%" cellspacing="0" cellpadding="0">{rows}</table>'
        f'<p style="font-size:12px;color:#6b7280;margin-top:16px">{e(t["off"])} '
        f'<a href="{e(off)}">{e(off)}</a></p></div>'
    )
    return subject, "\n".join(lines), page, off


def _local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.digest_tz))


async def send_one(db: AsyncSession, user: User, today: date) -> bool:
    digest = await build(db, user)
    sent = False
    if digest["items"]:
        subject, text, page, off = render(user, digest)
        sent = await mailer.send(
            user.email,
            subject,
            text,
            page,
            headers={
                "List-Unsubscribe": f"<{off}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
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
            try:
                sent += int(await send_one(db, user, today))
            except Exception:  # noqa: BLE001 - one user's problem doesn't stop the rest
                log.exception("digest for %s failed", user.id)
        # An hour ahead: queue AI summaries (low priority) for the next round
        # of digests, so the email shows summaries rather than excerpts.
        soon = (now.hour + 1) % 24
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
