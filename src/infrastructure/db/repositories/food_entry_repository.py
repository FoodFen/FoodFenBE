"""Concrete ``FoodEntryRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from uuid import UUID

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
