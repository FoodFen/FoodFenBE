"""Concrete ``FoodEntryRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.food_entry import FoodEntry
from src.infrastructure.db.models.food_entry_model import FoodEntryORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyFoodEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entry: FoodEntry) -> FoodEntry:
        row = await create_idempotent(self._session, FoodEntryORM.from_domain(entry), FoodEntryORM)
        return row.to_domain()

    async def get_by_id(self, entry_id: UUID) -> FoodEntry | None:
        row = await self._session.get(FoodEntryORM, entry_id)
        if row is None or row.deleted_at is not None:
            return None
        return row.to_domain()

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[FoodEntry]:
        rows = (
            await self._session.execute(
                select(FoodEntryORM).where(
                    FoodEntryORM.user_id == user_id,
                    FoodEntryORM.logged_on >= from_date,
                    FoodEntryORM.logged_on <= to_date,
                    FoodEntryORM.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
