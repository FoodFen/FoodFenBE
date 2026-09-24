"""Shared idempotent-create helper for tables with a ``(user_id, client_id)``
unique constraint — see
docs/superpowers/specs/2026-09-24-diary-sync-push-design.md.
"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

_Row = TypeVar("_Row")


async def create_idempotent(session: AsyncSession, row: _Row, model: type[_Row]) -> _Row:
    """Insert ``row``. If its ``(user_id, client_id)`` was already used by an
    earlier request, return that existing row instead of raising — a retried
    request after a dropped response must not create a duplicate. Relies on
    the DB's own unique constraint (race-safe against a concurrent retry),
    not a check-then-insert.

    If the conflict wasn't actually a ``client_id`` repeat (e.g. a different
    unique constraint on the same table fired), the re-query finds nothing
    and the original error is re-raised rather than masked.
    """
    session.add(row)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await session.execute(
            select(model).where(model.user_id == row.user_id, model.client_id == row.client_id)
        )
        found = existing.scalar_one_or_none()
        if found is None:
            raise
        return found
    await session.refresh(row)
    return row
