"""Rescue access when an editor or admin lost both their authenticator and their
recovery codes. Only from the server: no web page can do this.

Turns their one-time codes off and signs them out everywhere; at the next visit
to the administration they set up new ones (QR + recovery codes).

Run inside the backend container:
    docker compose exec backend python -m app.scripts.reset_totp you@example.com
"""

from __future__ import annotations

import argparse
import asyncio

from app.db.session import SessionLocal
from app.services import auth as auth_service
from app.services import staff_totp


async def main(email: str) -> int:
    async with SessionLocal() as db:
        user = await auth_service.get_user_by_email(db, email)
        if user is None:
            print(f"No account with email {email!r}.")
            return 1
        await staff_totp.disable(db, user)
        user.token_version += 1
        await db.commit()
        print(f"One-time codes turned off for {user.email}; they must set them up again.")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.email)))
