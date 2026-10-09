"""Shared entry point: --env-file, target-host print, one transaction."""

from __future__ import annotations

import argparse
import asyncio
import os


def main(parser: argparse.ArgumentParser, run) -> None:
    """Parse args, point at the DB, then ``run(session, args)`` (returns lines to print) in one transaction."""
    parser.add_argument("--env-file", help="load DATABASE_URL from this file (default: env / .env)")
    args = parser.parse_args()
    if args.env_file:
        from dotenv import dotenv_values  # ships with pydantic-settings

        url = dotenv_values(args.env_file).get("DATABASE_URL")
        if not url:
            parser.error(f"no DATABASE_URL in {args.env_file}")
        os.environ["DATABASE_URL"] = url  # before `src` is imported: settings reads it at import
    asyncio.run(_go(run, args))


async def _go(run, args: argparse.Namespace) -> None:
    from src.infrastructure.db.session import SessionLocal, engine

    print(f"target host: {engine.url.host}")  # never the URL itself: it carries the password
    try:
        async with SessionLocal() as session:
            try:
                lines = await run(session, args)
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        print("\n".join(lines))
    finally:
        await engine.dispose()
