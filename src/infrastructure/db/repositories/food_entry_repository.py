"""Concrete ``FoodEntryRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.food_entry import FoodEntry
from src.domain.exceptions import FoodEntryNotFoundException
from src.infrastructure.db.models.food_entry_model import FoodEntryORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyFoodEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, entry: FoodEntry) -> FoodEntry:
        row = await create_idempotent(self._session, FoodEntryORM.from_domain(entry), FoodEntryORM)
        if row.deleted_at is not None:
            # create_idempotent resolved this client_id to a row the user
            # has since deleted — handing back that stale data as a fresh
            # 200 would look like a successful create of live data.
            raise FoodEntryNotFoundException(f"no food entry for client_id {entry.client_id!r}")
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

    async def update(self, entry: FoodEntry) -> FoodEntry:
        row = await self._session.get(FoodEntryORM, entry.id)
        if row is None or row.deleted_at is not None:
            raise FoodEntryNotFoundException(f"no food entry {entry.id}")
        fresh = FoodEntryORM.from_domain(entry)
        for column in FoodEntryORM.__table__.columns.keys():
            if column not in ("id", "deleted_at"):
                setattr(row, column, getattr(fresh, column))
        row.ingredients = fresh.ingredients
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()

    async def delete(self, entry_id: UUID) -> None:
        row = await self._session.get(FoodEntryORM, entry_id)
        if row is None or row.deleted_at is not None:
            raise FoodEntryNotFoundException(f"no food entry {entry_id}")
        row.deleted_at = datetime.now(UTC)
        await self._session.flush()
