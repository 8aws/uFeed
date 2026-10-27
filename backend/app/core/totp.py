"""One-time codes (RFC 6238, SHA-1, 6 digits, 30 s) for editors and admins, and
the small helpers around them: the sealed secret and the recovery codes.

Standard parameters on purpose: every authenticator app and password manager
(1Password, Bitwarden, Apple Passwords, Google Authenticator...) understands them.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

STEP_S = 30
DIGITS = 6
WINDOW = 1  # steps accepted either side of now: clocks drift a little
RECOVERY_CODES = 10
# No 0/O/1/I/L: codes are read from paper and typed.
_RECOVERY_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_secret() -> str:
    """160 bits, base32 without padding (what authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    return base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)


def code_at(secret: str, step: int) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**DIGITS).zfill(DIGITS)


def current_step(now: float | None = None) -> int:
    return int((time.time() if now is None else now) // STEP_S)


def check_code(
    secret: str, code: str, last_step: int | None, now: float | None = None
) -> int | None:
    """The step the code belongs to, or None. A step at or before `last_step`
    (already used) is refused, so a code seen over a shoulder works once."""
    code = "".join(code.split())
    if len(code) != DIGITS or not code.isdigit():
        return None
    here = current_step(now)
    for step in range(here - WINDOW, here + WINDOW + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def otpauth_url(secret: str, account: str, issuer: str | None = None) -> str:
    issuer = issuer or settings.totp_issuer
    label = quote(f"{issuer}:{account}", safe="")
    query = urlencode({"secret": secret, "issuer": issuer, "digits": DIGITS, "period": STEP_S})
    return f"otpauth://totp/{label}?{query}"


# --- Secret at rest ------------------------------------------------------------


def _fernet() -> Fernet:
    seed = settings.secretbox_key or f"ufeed-secretbox:{settings.jwt_secret}"
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(seed.encode()).digest()))


def seal(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def unseal(sealed: str) -> str | None:
    try:
        return _fernet().decrypt(sealed.encode()).decode()
    except InvalidToken:
        return None


# --- Recovery codes ------------------------------------------------------------


def new_recovery_codes() -> list[str]:
    def one() -> str:
        raw = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(10))
        return f"{raw[:5]}-{raw[5:]}"

    return [one() for _ in range(RECOVERY_CODES)]


def normalize_recovery(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def hash_recovery(code: str) -> str:
    # ~50 bits of randomness and single use: a plain keyed hash is enough.
    return hmac.new(
        settings.jwt_secret.encode(), normalize_recovery(code).encode(), hashlib.sha256
    ).hexdigest()


def looks_like_recovery(code: str) -> bool:
    return len(normalize_recovery(code)) == 10
