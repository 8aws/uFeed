"""Rescue access when nobody can sign in (e.g. the only admin forgot it).

Sets a random temporary password (printed once), signs the account out
everywhere and asks the user to change it at next sign-in.

Run inside the backend container:
    docker compose exec backend python -m app.scripts.reset_password you@example.com
    ... --admin   also make the account an administrator (and re-enable it)
"""

from __future__ import annotations

import argparse
import asyncio

from app.db.session import SessionLocal
from app.services import auth as auth_service


async def main(email: str, make_admin: bool) -> int:
    async with SessionLocal() as db:
        user = await auth_service.get_user_by_email(db, email)
        if user is None:
            print(f"No account with email {email!r}.")
            return 1
        if make_admin:
            user.role = "admin"
            user.is_active = True
        temp = auth_service.temporary_password()
        await auth_service.set_password(db, user, temp, must_change=True)
        print(f"Temporary password for {user.email}: {temp}")
        print("They will be asked to change it after signing in.")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("email")
    parser.add_argument("--admin", action="store_true", help="also grant admin and re-enable")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.email, args.admin)))
