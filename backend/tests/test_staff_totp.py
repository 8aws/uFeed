from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import totp
from app.core.config import settings
from tests.test_admin import _h, _register, _set_role

# RFC 6238 appendix B (SHA-1, secret "12345678901234567890"), last 6 digits.
RFC_SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"


def test_rfc6238_vectors() -> None:
    assert totp.code_at(RFC_SECRET, 59 // 30) == "287082"
    assert totp.code_at(RFC_SECRET, 1111111109 // 30) == "081804"
    assert totp.code_at(RFC_SECRET, 2000000000 // 30) == "279037"


def test_code_is_accepted_once_and_only_nearby() -> None:
    now = 1_700_000_000.0
    step = totp.current_step(now)
    code = totp.code_at(RFC_SECRET, step)
    assert totp.check_code(RFC_SECRET, code, None, now) == step
    assert totp.check_code(RFC_SECRET, code, step, now) is None  # already used
    assert totp.check_code(RFC_SECRET, f" {code[:3]} {code[3:]} ", None, now) == step
    assert totp.check_code(RFC_SECRET, totp.code_at(RFC_SECRET, step + 1), None, now) == step + 1
    assert totp.check_code(RFC_SECRET, totp.code_at(RFC_SECRET, step + 5), None, now) is None
    assert totp.check_code(RFC_SECRET, "12345", None, now) is None
    assert totp.check_code(RFC_SECRET, "abcdef", None, now) is None


def test_secret_is_sealed_and_link_is_standard() -> None:
    secret = totp.generate_secret()
    sealed = totp.seal(secret)
    assert secret not in sealed
    assert totp.unseal(sealed) == secret
    assert totp.unseal("not a sealed value") is None
    url = totp.otpauth_url(secret, "ed+x@example.com")
    assert url.startswith("otpauth://totp/uFeed%3Aed%2Bx%40example.com?")
    assert f"secret={secret}" in url and "issuer=uFeed" in url and "digits=6" in url


def test_recovery_codes_are_typeable_and_hash_ignores_dashes_and_case() -> None:
    codes = totp.new_recovery_codes()
    assert len(set(codes)) == 10
    code = codes[0]
    assert len(code) == 11 and code[5] == "-"
    assert totp.hash_recovery(code) == totp.hash_recovery(code.lower().replace("-", " "))
    assert totp.looks_like_recovery(code) and not totp.looks_like_recovery("123456")


async def _staff(api: AsyncClient, db: AsyncSession, role: str) -> dict:
    r = await _register(api)
    await _set_role(db, r.json()["user"]["id"], role)
    return _h(r)


async def _enrol(api: AsyncClient, h: dict) -> tuple[str, dict]:
    """Set up codes for the account; returns (secret, enable response)."""
    setup = await api.post("/api/staff/totp/setup", headers=h)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    code = totp.code_at(secret, totp.current_step())
    enabled = await api.post("/api/staff/totp/enable", headers=h, json={"code": code})
    assert enabled.status_code == 200, enabled.text
    return secret, enabled.json()


def _next_code(secret: str) -> str:
    # The step after the one the previous code used (a code works once).
    return totp.code_at(secret, totp.current_step() + 1)


@pytest.fixture
def on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "staff_totp", True)


async def test_only_staff_can_enrol(api: AsyncClient, db_session: AsyncSession, on) -> None:
    h = await _staff(api, db_session, "vip")
    assert (await api.get("/api/staff/totp", headers=h)).status_code == 403
    assert (await api.post("/api/staff/totp/setup", headers=h)).status_code == 403


async def test_admin_needs_codes_before_anything(
    api: AsyncClient, db_session: AsyncSession, on
) -> None:
    h = await _staff(api, db_session, "admin")
    r = await api.get("/api/admin/users", headers=h)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "totp_enrol_required"

    status = (await api.get("/api/staff/totp", headers=h)).json()
    assert status == {"enabled": False, "pending": False, "required": True, "recovery_left": 0}

    secret, enabled = await _enrol(api, h)
    assert len(enabled["recovery_codes"]) == 10
    # Enrolling already proves the code: the session is open.
    ok = {**h, "X-Step-Up": enabled["step_up_token"]}
    assert (await api.get("/api/admin/users", headers=ok)).status_code == 200

    # Without the proof (a stolen bearer token alone) the admin stays closed.
    r = await api.get("/api/admin/users", headers=h)
    assert r.status_code == 403 and r.json()["error"]["code"] == "totp_required"
    r = await api.get("/api/admin/users", headers={**h, "X-Step-Up": "junk"})
    assert r.json()["error"]["code"] == "totp_required"

    # The code that enrolled can't be used again, the next one can.
    again = totp.code_at(secret, totp.current_step())
    r = await api.post("/api/staff/totp/verify", headers=h, json={"code": again})
    assert r.status_code == 403 and r.json()["error"]["code"] == "invalid_code"
    r = await api.post("/api/staff/totp/verify", headers=h, json={"code": _next_code(secret)})
    assert r.status_code == 200, r.text
    proof = {**h, "X-Step-Up": r.json()["step_up_token"]}
    assert (await api.get("/api/admin/settings", headers=proof)).status_code == 200


async def test_proof_belongs_to_one_account(api: AsyncClient, db_session: AsyncSession, on) -> None:
    a = await _staff(api, db_session, "admin")
    b = await _staff(api, db_session, "admin")
    _, enabled_a = await _enrol(api, a)
    await _enrol(api, b)
    r = await api.get("/api/admin/users", headers={**b, "X-Step-Up": enabled_a["step_up_token"]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "totp_required"


async def test_risky_actions_want_a_fresh_code(
    api: AsyncClient, db_session: AsyncSession, on, monkeypatch: pytest.MonkeyPatch
) -> None:
    h = await _staff(api, db_session, "admin")
    _, enabled = await _enrol(api, h)
    proof = {**h, "X-Step-Up": enabled["step_up_token"]}
    body = {"registration_open": False}
    assert (await api.patch("/api/admin/settings", headers=proof, json=body)).status_code == 200
    # Any proof older than the allowed age is "not fresh" for these.
    monkeypatch.setattr(settings, "staff_fresh_s", -1)
    r = await api.patch("/api/admin/settings", headers=proof, json=body)
    assert r.status_code == 403 and r.json()["error"]["code"] == "totp_fresh_required"
    # ...while reading and the routine moderation still work with the session.
    assert (await api.get("/api/admin/settings", headers=proof)).status_code == 200


async def test_editor_curation_asks_for_codes_too(
    api: AsyncClient, db_session: AsyncSession, on
) -> None:
    h = await _staff(api, db_session, "editor")
    r = await api.get("/api/curation/sources", headers=h)
    assert r.json()["error"]["code"] == "totp_enrol_required"
    _, enabled = await _enrol(api, h)
    r = await api.get("/api/curation/sources", headers={**h, "X-Step-Up": enabled["step_up_token"]})
    assert r.status_code == 200
    # An editor is still no admin, with or without the code.
    r = await api.get("/api/admin/users", headers={**h, "X-Step-Up": enabled["step_up_token"]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"


async def test_wrong_code_and_pending_setup(api: AsyncClient, db_session: AsyncSession, on) -> None:
    h = await _staff(api, db_session, "admin")
    setup = await api.post("/api/staff/totp/setup", headers=h)
    secret = setup.json()["secret"]
    assert (await api.get("/api/staff/totp", headers=h)).json()["pending"] is True
    r = await api.post("/api/staff/totp/enable", headers=h, json={"code": "000000"})
    assert r.status_code == 403
    # Not confirmed yet: the admin is still closed.
    r = await api.get("/api/admin/users", headers=h)
    assert r.json()["error"]["code"] == "totp_enrol_required"
    # Starting over replaces the pending secret.
    other = (await api.post("/api/staff/totp/setup", headers=h)).json()["secret"]
    assert other != secret
    bad = totp.code_at(secret, totp.current_step())
    r = await api.post("/api/staff/totp/enable", headers=h, json={"code": bad})
    assert r.status_code == 403
    good = totp.code_at(other, totp.current_step())
    assert (
        await api.post("/api/staff/totp/enable", headers=h, json={"code": good})
    ).status_code == 200
    assert (await api.post("/api/staff/totp/setup", headers=h)).status_code == 409


async def test_recovery_code_works_once(api: AsyncClient, db_session: AsyncSession, on) -> None:
    h = await _staff(api, db_session, "admin")
    _, enabled = await _enrol(api, h)
    code = enabled["recovery_codes"][0]
    r = await api.post("/api/staff/totp/verify", headers=h, json={"code": code.lower()})
    assert r.status_code == 200, r.text
    again = await api.post("/api/staff/totp/verify", headers=h, json={"code": code})
    assert again.status_code == 403
    assert (await api.get("/api/staff/totp", headers=h)).json()["recovery_left"] == 9


async def test_new_recovery_codes_replace_the_old(
    api: AsyncClient, db_session: AsyncSession, on
) -> None:
    h = await _staff(api, db_session, "admin")
    secret, enabled = await _enrol(api, h)
    old = enabled["recovery_codes"][1]
    r = await api.post(
        "/api/staff/totp/recovery-codes", headers=h, json={"code": _next_code(secret)}
    )
    assert r.status_code == 200, r.text
    fresh = r.json()["recovery_codes"]
    assert len(fresh) == 10 and old not in fresh
    r = await api.post("/api/staff/totp/verify", headers=h, json={"code": old})
    assert r.status_code == 403
    r = await api.post("/api/staff/totp/verify", headers=h, json={"code": fresh[0]})
    assert r.status_code == 200


async def test_disable_needs_code_and_password(
    api: AsyncClient, db_session: AsyncSession, on
) -> None:
    h = await _staff(api, db_session, "admin")
    secret, _ = await _enrol(api, h)
    r = await api.post(
        "/api/staff/totp/disable", headers=h, json={"code": _next_code(secret), "password": "nope"}
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "invalid_credentials"
    r = await api.post(
        "/api/staff/totp/disable",
        headers=h,
        json={"code": _next_code(secret), "password": "supersecret1"},
    )
    assert r.status_code == 200, r.text
    status = (await api.get("/api/staff/totp", headers=h)).json()
    assert status["enabled"] is False and status["recovery_left"] == 0


async def test_password_change_ends_the_proof(
    api: AsyncClient, db_session: AsyncSession, on
) -> None:
    from sqlalchemy import update

    from app.models.user import User

    h = await _staff(api, db_session, "admin")
    me = (await api.get("/api/me", headers=h)).json()
    _, enabled = await _enrol(api, h)
    proof = {**h, "X-Step-Up": enabled["step_up_token"]}
    assert (await api.get("/api/admin/users", headers=proof)).status_code == 200
    import uuid

    await db_session.execute(
        update(User)
        .where(User.id == uuid.UUID(me["id"]))
        .values(token_version=User.token_version + 1)
    )
    await db_session.commit()
    # The access token dies with the version bump; so does the step-up one.
    assert (await api.get("/api/admin/users", headers=proof)).status_code == 401
