"""Concrete ``ActivityLogRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.activity_log import ActivityLog
from src.infrastructure.db.models.activity_log_model import ActivityLogORM


class SQLAlchemyActivityLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

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
