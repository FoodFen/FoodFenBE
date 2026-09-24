"""Concrete ``WaterLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.water_log import WaterLog
from src.infrastructure.db.models.water_log_model import WaterLogORM


class SQLAlchemyWaterLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WaterLog]:
        rows = (
            await self._session.execute(
                select(WaterLogORM).where(
                    WaterLogORM.user_id == user_id,
                    WaterLogORM.logged_on >= from_date,
                    WaterLogORM.logged_on <= to_date,
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
