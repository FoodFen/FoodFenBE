"""Concrete ``FoodEntryRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.food_entry import FoodEntry
from src.infrastructure.db.models.food_entry_model import FoodEntryORM


class SQLAlchemyFoodEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entry: FoodEntry) -> FoodEntry:
        row = FoodEntryORM.from_domain(entry)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()

    async def get_by_id(self, entry_id: UUID) -> FoodEntry | None:
        row = await self._session.get(FoodEntryORM, entry_id)
        return row.to_domain() if row is not None else None

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[FoodEntry]:
        rows = (
            await self._session.execute(
                select(FoodEntryORM).where(
                    FoodEntryORM.user_id == user_id,
                    FoodEntryORM.logged_on >= from_date,
                    FoodEntryORM.logged_on <= to_date,
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
