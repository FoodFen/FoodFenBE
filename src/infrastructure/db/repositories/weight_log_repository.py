"""Concrete ``WeightLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.weight_log import WeightLog
from src.infrastructure.db.models.weight_log_model import WeightLogORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyWeightLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: WeightLog) -> WeightLog:
        row = await create_idempotent(self._session, WeightLogORM.from_domain(log), WeightLogORM)
        return row.to_domain()

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WeightLog]:
        rows = (
            await self._session.execute(
                select(WeightLogORM).where(
                    WeightLogORM.user_id == user_id,
                    WeightLogORM.recorded_at >= from_date,
                    WeightLogORM.recorded_at <= to_date,
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
