"""Outgoing email (password resets, the daily digest) through an SMTP relay.

On the NAS that's the Postfix relay on the host (it forwards to the mail
provider); it accepts uverse.es senders from the Docker networks without a
login. Mail is off when SMTP_HOST is empty (development, tests).
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, parseaddr

from app.core.config import settings

log = logging.getLogger("ufeed.mail")


def enabled() -> bool:
    return bool(settings.smtp_host)


def _build(
    to: str, subject: str, text: str, html: str | None, headers: dict[str, str] | None
) -> EmailMessage:
    msg = EmailMessage()
    name, addr = parseaddr(settings.mail_from)
    msg["From"] = formataddr((name or "uFeed", addr))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=addr.split("@")[-1] or None)
    for k, v in (headers or {}).items():
        msg[k] = v
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def _send_sync(msg: EmailMessage) -> None:
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        smtp.ehlo()
        if settings.smtp_starttls:
            smtp.starttls()
            smtp.ehlo()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


async def send(
    to: str,
    subject: str,
    text: str,
    html: str | None = None,
    headers: dict[str, str] | None = None,
) -> bool:
    """Send one message; False (and logged) if mail is off or it failed."""
    if not enabled():
        log.info("mail disabled; not sent: %s", subject)
        return False
    try:
        await asyncio.to_thread(_send_sync, _build(to, subject, text, html, headers))
        return True
    except (OSError, smtplib.SMTPException) as exc:
        log.warning("mail to %s failed: %s", to.split("@")[-1], exc)
        return False
