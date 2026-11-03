"""The audit log: one line per administration/curation action."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import Request
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.audit_entry import AuditEntry
from app.models.user import User
from app.services.moderation import now


def client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host[:45]


async def record(
    db: AsyncSession,
    request: Request | None,
    actor: User,
    action: str,
    target: User | None = None,
    *,
    target_email: str | None = None,
    **detail: Any,
) -> None:
    """Add the entry and commit it. Call it after the action succeeded.
    Never put secrets (passwords, codes, tokens) in `detail`."""
    db.add(
        AuditEntry(
            actor_id=actor.id,
            actor_email=actor.email,
            action=action,
            target_id=target.id if target else None,
            target_email=target.email if target else target_email,
            detail={k: v for k, v in detail.items() if v is not None},
            ip=client_ip(request),
        )
    )
    await db.commit()


async def page(
    db: AsyncSession,
    *,
    kind: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditEntry], int]:
    """Newest first. `kind` is the part before the dot ("user", "staff"...)."""
    where = []
    if kind:
        where.append(AuditEntry.action.like(f"{kind}.%"))
    if q:
        like = f"%{q.strip().lower()}%"
        where.append(
            or_(
                func.lower(AuditEntry.actor_email).like(like),
                func.lower(func.coalesce(AuditEntry.target_email, "")).like(like),
            )
        )
    total = await db.scalar(select(func.count()).select_from(AuditEntry).where(*where))
    rows = (
        (
            await db.execute(
                select(AuditEntry)
                .where(*where)
                .order_by(AuditEntry.created_at.desc(), AuditEntry.id)
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return list(rows), int(total or 0)


async def purge_old(db: AsyncSession, days: int | None = None) -> int:
    days = settings.audit_retention_days if days is None else days
    if days <= 0:
        return 0
    result = await db.execute(
        delete(AuditEntry).where(AuditEntry.created_at < now() - timedelta(days=days))
    )
    await db.commit()
    return result.rowcount or 0
