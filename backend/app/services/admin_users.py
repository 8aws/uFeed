"""The admin's view of the user base: filtered, sorted and paged by the
database (never the whole list at once), and counted for the summary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.ban import Ban
from app.models.subscription import Subscription
from app.models.user import User
from app.services import moderation

Status = Literal["active", "disabled", "suspended", "banned", "dormant"]
Guests = Literal["hide", "only", "all"]
Sort = Literal["created", "activity", "feeds", "email"]


def _banned():
    now = moderation.now()
    return (
        select(Ban.id)
        .where(Ban.email == User.email, or_(Ban.until.is_(None), Ban.until > now))
        .exists()
    )


def _conditions(
    *,
    q: str | None,
    role: str | None,
    status: Status | None,
    guests: Guests,
    inactive_days: int | None,
):
    now = moderation.now()
    conds = []
    if guests == "hide":
        conds.append(User.is_guest.is_(False))
    elif guests == "only":
        conds.append(User.is_guest.is_(True))
    if q:
        like = f"%{q.strip()}%"
        conds.append(or_(User.email.ilike(like), User.display_name.ilike(like)))
    if role:
        conds.append(User.role == role)
    if status == "active":
        conds += [
            User.is_active.is_(True),
            User.dormant_since.is_(None),
            or_(User.suspended_until.is_(None), User.suspended_until <= now),
            ~_banned(),
        ]
    elif status == "disabled":
        conds.append(User.is_active.is_(False))
    elif status == "suspended":
        conds.append(User.suspended_until > now)
    elif status == "banned":
        conds.append(_banned())
    elif status == "dormant":
        conds.append(User.dormant_since.isnot(None))
    if inactive_days:
        conds.append(moderation.last_activity_expr() < now - timedelta(days=inactive_days))
    return conds


@dataclass(slots=True)
class UserRow:
    user: User
    feeds: int
    activity: object


async def page(
    db: AsyncSession,
    *,
    q: str | None = None,
    role: str | None = None,
    status: Status | None = None,
    guests: Guests = "hide",
    inactive_days: int | None = None,
    sort: Sort = "created",
    descending: bool = True,
    limit: int = 25,
    offset: int = 0,
) -> tuple[list[UserRow], int, dict]:
    """One page of users plus how many match; the ban of each row is looked up
    for just that page."""
    conds = _conditions(q=q, role=role, status=status, guests=guests, inactive_days=inactive_days)
    feeds = (
        select(Subscription.user_id, func.count().label("n"))
        .group_by(Subscription.user_id)
        .subquery()
    )
    feeds_n = func.coalesce(feeds.c.n, 0)
    activity = moderation.last_activity_expr()
    key = {
        "created": User.created_at,
        "activity": activity,
        "feeds": feeds_n,
        "email": func.lower(User.email),
    }[sort]
    stmt = (
        select(User, feeds_n, activity)
        .outerjoin(feeds, feeds.c.user_id == User.id)
        .where(*conds)
        .order_by(key.desc() if descending else key.asc(), User.id)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()
    total = int(await db.scalar(select(func.count()).select_from(User).where(*conds)) or 0)
    emails = [u.email for u, _, _ in rows]
    now = moderation.now()
    bans = {}
    if emails:
        found = await db.execute(
            select(Ban).where(Ban.email.in_(emails), or_(Ban.until.is_(None), Ban.until > now))
        )
        bans = {b.email: b for b in found.scalars()}
    return [UserRow(u, int(n or 0), act) for u, n, act in rows], total, bans


async def summary(db: AsyncSession) -> dict:
    now = moderation.now()
    reg = User.is_guest.is_(False)
    act = moderation.last_activity_expr()

    def count(*conds):
        return func.count().filter(and_(*conds)) if conds else func.count()

    row = (
        await db.execute(
            select(
                count(reg),
                count(reg, User.created_at > now - timedelta(days=7)),
                count(reg, act > now - timedelta(days=7), User.dormant_since.is_(None)),
                count(reg, act > now - timedelta(days=30), User.dormant_since.is_(None)),
                count(reg, User.dormant_since.isnot(None)),
                count(reg, User.suspended_until > now),
                count(reg, User.is_active.is_(False)),
                count(User.is_guest.is_(True)),
                count(User.is_guest.is_(True), User.created_at > now - timedelta(days=1)),
                count(User.is_guest.is_(True), User.created_at > now - timedelta(days=7)),
                count(User.is_guest.is_(True), act < now - timedelta(days=30)),
            )
        )
    ).one()
    by_role = {
        r: int(n)
        for r, n in (
            await db.execute(select(User.role, func.count()).where(reg).group_by(User.role))
        ).all()
    }
    banned = await db.scalar(select(func.count()).select_from(User).where(reg, _banned()))
    return {
        "users": int(row[0]),
        "by_role": by_role,
        "new_7d": int(row[1]),
        "active_7d": int(row[2]),
        "active_30d": int(row[3]),
        "dormant": int(row[4]),
        "suspended": int(row[5]),
        "banned": int(banned or 0),
        "disabled": int(row[6]),
        "guests": int(row[7]),
        "guests_today": int(row[8]),
        "guests_7d": int(row[9]),
        "guests_idle_30d": int(row[10]),
        "guest_daily_cap": settings.guest_max_per_day,
    }
