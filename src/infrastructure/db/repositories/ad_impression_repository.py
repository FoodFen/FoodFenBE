"""Concrete ``AdImpressionRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models.ad_impression_model import AdImpressionORM


class SQLAlchemyAdImpressionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def increment(self, restaurant_ids: Sequence[UUID], day: date) -> None:
        for restaurant_id in restaurant_ids:
            await self._session.execute(
                pg_insert(AdImpressionORM)
                .values(restaurant_id=restaurant_id, day=day, count=1)
                .on_conflict_do_update(
                    index_elements=["restaurant_id", "day"],
                    set_={"count": AdImpressionORM.count + 1},
                )
            )

    async def counts(self, restaurant_id: UUID, first: date, last: date) -> dict[date, int]:
        rows = await self._session.execute(
            select(AdImpressionORM.day, AdImpressionORM.count).where(
                AdImpressionORM.restaurant_id == restaurant_id,
                AdImpressionORM.day >= first,
                AdImpressionORM.day <= last,
            )
        )
        return {day: count for day, count in rows}
