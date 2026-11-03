from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import totp
from app.core.config import settings
from app.models.audit_entry import AuditEntry
from app.services import audit
from app.services.moderation import now
from tests.test_admin import _h, _register, _set_role
from tests.test_admin_users import _user
from tests.test_reader import _seed_source


async def _admin_headers(api: AsyncClient, db: AsyncSession) -> tuple[dict, str]:
    r = await _register(api)
    await _set_role(db, r.json()["user"]["id"], "admin")
    return _h(r), r.json()["user"]["email"]


async def _log(api: AsyncClient, h: dict, **params) -> dict:
    r = await api.get("/api/admin/audit", headers=h, params=params)
    assert r.status_code == 200, r.text
    return r.json()


async def test_only_admins_read_the_log(api: AsyncClient, db_session: AsyncSession) -> None:
    r = await _register(api)
    await _set_role(db_session, r.json()["user"]["id"], "editor")
    assert (await api.get("/api/admin/audit", headers=_h(r))).status_code == 403


async def test_moderation_leaves_a_trail(api: AsyncClient, db_session: AsyncSession) -> None:
    h, admin_email = await _admin_headers(api, db_session)
    target = await _user(db_session, "victim")

    r = await api.patch(f"/api/admin/users/{target.id}", headers=h, json={"role": "vip"})
    assert r.status_code == 200, r.text
    r = await api.post(f"/api/admin/users/{target.id}/suspend", headers=h, json={"days": 3})
    assert r.status_code == 200, r.text
    r = await api.post(
        f"/api/admin/users/{target.id}/ban", headers=h, json={"days": 7, "reason": "spam"}
    )
    assert r.status_code == 200, r.text
    assert (
        await api.post(f"/api/admin/users/{target.id}/reset-password", headers=h)
    ).status_code == 200

    page = await _log(api, h, q=admin_email)
    by_action = {e["action"]: e for e in page["items"]}
    assert {"user.role", "user.suspend", "user.ban", "user.reset_password"} <= set(by_action)
    role = by_action["user.role"]
    assert role["actor_email"] == admin_email and role["target_email"] == target.email
    assert role["detail"] == {"from": "general", "to": "vip"} or role["detail"]["to"] == "vip"
    assert by_action["user.ban"]["detail"] == {"days": 7, "reason": "spam"}
    assert by_action["user.suspend"]["detail"] == {"days": 3}
    # Newest first.
    stamps = [e["created_at"] for e in page["items"]]
    assert stamps == sorted(stamps, reverse=True)
    # The temporary password itself must never be written down.
    assert "temporary" not in str(page).lower()


async def test_deleting_an_account_keeps_who_it_was(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    h, admin_email = await _admin_headers(api, db_session)
    target = await _user(db_session, "gone")
    email = target.email
    assert (await api.delete(f"/api/admin/users/{target.id}", headers=h)).status_code == 200
    entry = (await _log(api, h, kind="user", q=admin_email))["items"][0]
    assert entry["action"] == "user.delete" and entry["target_email"] == email


async def test_settings_and_filters(api: AsyncClient, db_session: AsyncSession) -> None:
    h, admin_email = await _admin_headers(api, db_session)
    r = await api.patch("/api/admin/settings", headers=h, json={"registration_open": False})
    assert r.status_code == 200
    target = await _user(db_session, "findme")
    await api.post(f"/api/admin/users/{target.id}/suspend", headers=h, json={"days": 1})

    only_settings = await _log(api, h, kind="settings", q=admin_email)
    assert [e["action"] for e in only_settings["items"]] == ["settings.update"]
    assert only_settings["items"][0]["detail"] == {"registration_open": False}

    by_target = await _log(api, h, q=target.email[:12].upper())
    assert [e["action"] for e in by_target["items"]] == ["user.suspend"]

    paged = await _log(api, h, q=admin_email, limit=1)
    assert len(paged["items"]) == 1 and paged["total"] >= 2


async def test_curation_actions_are_logged(api: AsyncClient, db_session: AsyncSession) -> None:
    h, admin_email = await _admin_headers(api, db_session)
    src = await _seed_source(db_session, [("Hello", "<p>x</p>")])
    await db_session.commit()
    r = await api.patch(f"/api/curation/sources/{src.id}", headers=h, json={"paused": True})
    assert r.status_code == 200, r.text
    entry = (await _log(api, h, kind="curation", q=admin_email))["items"][0]
    assert entry["action"] == "curation.pause"
    # Never the feed address (a feed with one follower may be private).
    assert "ex.com" not in str(entry)


async def test_codes_are_logged_without_the_codes(
    api: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "staff_totp", True)
    h, _ = await _admin_headers(api, db_session)
    setup = (await api.post("/api/staff/totp/setup", headers=h)).json()
    good = totp.code_at(setup["secret"], totp.current_step())
    bad = await api.post("/api/staff/totp/enable", headers=h, json={"code": "000000"})
    assert bad.status_code == 403
    ok = await api.post("/api/staff/totp/enable", headers=h, json={"code": good})
    proof = {**h, "X-Step-Up": ok.json()["step_up_token"]}
    assert (
        await api.post("/api/staff/totp/verify", headers=h, json={"code": "111111"})
    ).status_code == 403

    actions = [e["action"] for e in (await _log(api, proof, kind="staff"))["items"]]
    assert "staff.totp_enable" in actions and "staff.code_failed" in actions
    dump = str(await _log(api, proof))
    assert good not in dump and setup["secret"] not in dump


async def test_old_entries_are_purged(api: AsyncClient, db_session: AsyncSession) -> None:
    h, _ = await _admin_headers(api, db_session)
    old = AuditEntry(
        actor_email="old@example.com", action="user.ban", created_at=now() - timedelta(days=400)
    )
    db_session.add(old)
    await db_session.commit()
    await api.patch("/api/admin/settings", headers=h, json={"registration_open": True})
    assert await audit.purge_old(db_session, 365) == 1
    left = (await db_session.execute(select(AuditEntry.actor_email))).scalars().all()
    assert "old@example.com" not in left and len(left) >= 1
    assert await audit.purge_old(db_session, 0) == 0
