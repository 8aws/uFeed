from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    generate_api_key,
    hash_api_key,
    parse_api_key_prefix,
)
from app.models.api_key import ApiKey


async def create_api_key(
    db: AsyncSession, user_id: uuid.UUID, name: str, scopes: list[str]
) -> tuple[ApiKey, str]:
    """Create a key; returns (row, plaintext). Plaintext is shown only once."""
    plaintext, prefix, key_hash = generate_api_key()
    key = ApiKey(
        user_id=user_id,
        key_hash=key_hash,
        prefix=prefix,
        name=name,
        scopes=scopes,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key, plaintext


async def list_api_keys(db: AsyncSession, user_id: uuid.UUID) -> list[ApiKey]:
    result = await db.execute(
        select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_api_key(db: AsyncSession, user_id: uuid.UUID, key_id: uuid.UUID) -> bool:
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id))
    key = result.scalar_one_or_none()
    if key is None or key.revoked_at is not None:
        return False
    key.revoked_at = datetime.now(UTC)
    await db.commit()
    return True


async def resolve_api_key(db: AsyncSession, plaintext: str) -> ApiKey | None:
    """Return the active ApiKey matching a plaintext key, or None."""
    prefix = parse_api_key_prefix(plaintext)
    if prefix is None:
        return None
    result = await db.execute(
        select(ApiKey).where(ApiKey.prefix == prefix, ApiKey.revoked_at.is_(None))
    )
    for key in result.scalars().all():
        if key.key_hash == hash_api_key(plaintext):
            key.last_used_at = datetime.now(UTC)
            await db.commit()
            return key
    return None
