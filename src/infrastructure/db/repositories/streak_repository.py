"""Concrete ``StreakRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.streak import Streak
from src.infrastructure.db.models.streak_model import StreakORM


class SQLAlchemyStreakRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, streak: Streak) -> Streak:
        # One row per user_id — a singleton, so "create" always really means
        # "replace whatever's there". Try the insert first (SAVEPOINT-isolated)
        # and fall back to an update on conflict, rather than a check-then-insert race.
        row = StreakORM.from_domain(streak)
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError:
            existing = await self._session.execute(
                select(StreakORM).where(StreakORM.user_id == streak.user_id)
            )
            found = existing.scalar_one_or_none()
            if found is None:
                raise
            for column in StreakORM.__table__.columns.keys():
                if column != "id":
                    setattr(found, column, getattr(row, column))
            await self._session.flush()
            row = found
        await self._session.refresh(row)
        return row.to_domain()
