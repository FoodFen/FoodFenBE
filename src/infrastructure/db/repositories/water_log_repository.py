"""Concrete ``WaterLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.water_log import WaterLog
from src.domain.exceptions import WaterLogNotFoundException
from src.infrastructure.db.models.water_log_model import WaterLogORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyWaterLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: WaterLog) -> WaterLog:
        row = await create_idempotent(self._session, WaterLogORM.from_domain(log), WaterLogORM)
        return row.to_domain()

    async def get_by_id(self, log_id: UUID) -> WaterLog | None:
        row = await self._session.get(WaterLogORM, log_id)
        if row is None or row.deleted_at is not None:
            return None
        return row.to_domain()

    async def update(self, log: WaterLog) -> WaterLog:
        row = await self._session.get(WaterLogORM, log.id)
        if row is None or row.deleted_at is not None:
            raise WaterLogNotFoundException(f"no water log {log.id}")
        fresh = WaterLogORM.from_domain(log)
        for column in WaterLogORM.__table__.columns.keys():
            if column not in ("id", "deleted_at"):
                setattr(row, column, getattr(fresh, column))
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()

    async def delete(self, log_id: UUID) -> None:
        row = await self._session.get(WaterLogORM, log_id)
        if row is None or row.deleted_at is not None:
            raise WaterLogNotFoundException(f"no water log {log_id}")
        row.deleted_at = datetime.now(UTC)
        await self._session.flush()

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WaterLog]:
        rows = (
            await self._session.execute(
                select(WaterLogORM).where(
                    WaterLogORM.user_id == user_id,
                    WaterLogORM.logged_on >= from_date,
                    WaterLogORM.logged_on <= to_date,
                    WaterLogORM.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
