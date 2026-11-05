"""Concrete ``FoodMissRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.food_miss import FoodMiss
from src.domain.enums import FoodMissStatus
from src.infrastructure.db.models.food_miss_model import FoodMissORM


class SQLAlchemyFoodMissRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, misses: Sequence[tuple[str, str]], language: str, at: datetime) -> None:
        stmt = pg_insert(FoodMissORM).values(
            [
                dict(
                    id=uuid4(), key=key, name=name, language=language, count=1, first_seen_at=at,
                    last_seen_at=at, status=FoodMissStatus.OPEN, resolved_food_id=None,
                )
                for key, name in misses
            ]
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["key"],
            set_={"count": FoodMissORM.count + 1, "last_seen_at": stmt.excluded.last_seen_at},
        )
        # Savepoint: a failed statement must not poison the request's transaction (the trial consume is next).
        async with self._session.begin_nested():
            await self._session.execute(stmt)

    async def list(self, status: FoodMissStatus, offset: int, limit: int) -> tuple[list[FoodMiss], int]:
        total = await self._session.scalar(
            select(func.count()).select_from(FoodMissORM).where(FoodMissORM.status == status)
        )
        rows = await self._session.scalars(
            select(FoodMissORM)
            .where(FoodMissORM.status == status)
            .order_by(FoodMissORM.count.desc(), FoodMissORM.last_seen_at.desc(), FoodMissORM.id)
            .offset(offset)
            .limit(limit)
        )
        return [row.to_domain() for row in rows], total

    async def get(self, miss_id: UUID) -> FoodMiss | None:
        row = await self._session.get(FoodMissORM, miss_id)
        return row.to_domain() if row else None

    async def update(self, miss: FoodMiss) -> None:
        row = await self._session.get(FoodMissORM, miss.id)
        row.status, row.resolved_food_id = miss.status, miss.resolved_food_id
        await self._session.flush()

    async def resolve_open(self, keys: Collection[str], food_id: UUID) -> None:
        if not keys:
            return
        await self._session.execute(
            update(FoodMissORM)
            .where(FoodMissORM.status == FoodMissStatus.OPEN, FoodMissORM.key.in_(keys))
            .values(status=FoodMissStatus.RESOLVED, resolved_food_id=food_id)
        )
