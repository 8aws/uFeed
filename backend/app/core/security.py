from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]
API_KEY_PLAINTEXT_PREFIX = "uf"


# --- Passwords ---------------------------------------------------------------


def _pw_bytes(password: str) -> bytes:
    # bcrypt only considers the first 72 bytes; truncate explicitly so long
    # passwords never raise instead of silently ignoring the tail.
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_pw_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_pw_bytes(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


# --- JWT ---------------------------------------------------------------------


def _create_token(sub: str, token_type: TokenType, expires: timedelta, version: int = 0) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "type": token_type,
        "tv": version,
        "iat": int(now.timestamp()),
        "exp": int((now + expires).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_access_token(sub: str, version: int = 0) -> str:
    return _create_token(sub, "access", timedelta(minutes=settings.jwt_access_ttl_min), version)


def create_refresh_token(sub: str, version: int = 0) -> str:
    return _create_token(sub, "refresh", timedelta(days=settings.jwt_refresh_ttl_days), version)


def token_version_ok(payload: dict[str, Any], current: int) -> bool:
    """Tokens issued before a password change/reset carry an older version."""
    return int(payload.get("tv", 0)) == current


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


# --- API keys ----------------------------------------------------------------


def generate_api_key() -> tuple[str, str, str]:
    """Return (plaintext, prefix, key_hash).

    Plaintext format: ``uf_<prefix>_<secret>``. Only the hash and the prefix
    are stored; the plaintext is shown to the user exactly once.
    """
    prefix = secrets.token_hex(4)  # 8 hex chars, used for lookup + display
    secret = secrets.token_urlsafe(32)
    plaintext = f"{API_KEY_PLAINTEXT_PREFIX}_{prefix}_{secret}"
    return plaintext, prefix, hash_api_key(plaintext)


def hash_api_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()


def parse_api_key_prefix(plaintext: str) -> str | None:
    # maxsplit=2: the random secret may itself contain "_" (base64url alphabet),
    # so only split off the leading "uf" and the fixed-width prefix.
    parts = plaintext.split("_", 2)
    if len(parts) != 3 or parts[0] != API_KEY_PLAINTEXT_PREFIX:
        return None
    return parts[1]


def user_id_from_sub(sub: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(sub)
    except (ValueError, TypeError):
        return None
