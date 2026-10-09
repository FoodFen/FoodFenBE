"""Promote (or --revoke) existing accounts to admin. Never creates an account.

    uv run python -m scripts.make_admin you@example.com [--revoke] [--env-file .env.prod]
"""

from __future__ import annotations

import argparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def run(session: AsyncSession, emails: list[str], revoke: bool = False) -> list[str]:
    from src.domain.enums import UserRole
    from src.infrastructure.db.models.user_model import UserORM

    target = UserRole.USER if revoke else UserRole.ADMIN
    lines = []
    for email in emails:
        user = (
            await session.execute(select(UserORM).where(func.lower(UserORM.email) == email.strip().lower()))
        ).scalar_one_or_none()
        if user is None:
            lines.append(f"{email}: not found (sign up first)")
        elif user.role == target:
            lines.append(f"{email}: already {target.value}")
        else:
            user.role = target
            lines.append(f"{email}: {'revoked' if revoke else 'promoted'}")
    await session.flush()
    return lines


if __name__ == "__main__":
    from scripts._cli import main

    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("emails", nargs="+", metavar="EMAIL")
    p.add_argument("--revoke", action="store_true", help="demote back to user")
    main(p, lambda s, a: run(s, a.emails, a.revoke))
