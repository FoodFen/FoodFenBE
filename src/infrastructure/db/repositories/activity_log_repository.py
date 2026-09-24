"""Concrete ``ActivityLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.activity_log import ActivityLog
from src.domain.exceptions import ActivityLogNotFoundException
from src.infrastructure.db.models.activity_log_model import ActivityLogORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyActivityLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, log: ActivityLog) -> ActivityLog:
        row = await create_idempotent(
            self._session, ActivityLogORM.from_domain(log), ActivityLogORM
        )
        return row.to_domain()

    async def get_by_id(self, log_id: UUID) -> ActivityLog | None:
        row = await self._session.get(ActivityLogORM, log_id)
        return row.to_domain() if row is not None else None

    async def update(self, log: ActivityLog) -> ActivityLog:
        row = await self._session.get(ActivityLogORM, log.id)
        if row is None:
            raise ActivityLogNotFoundException(f"no activity log {log.id}")
        fresh = ActivityLogORM.from_domain(log)
        for column in ActivityLogORM.__table__.columns.keys():
            if column != "id":
                setattr(row, column, getattr(fresh, column))
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[ActivityLog]:
        rows = (
            await self._session.execute(
                select(ActivityLogORM).where(
                    ActivityLogORM.user_id == user_id,
                    ActivityLogORM.logged_on >= from_date,
                    ActivityLogORM.logged_on <= to_date,
                )
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
