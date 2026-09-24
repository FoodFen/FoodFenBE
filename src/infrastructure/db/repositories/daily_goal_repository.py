"""Concrete ``DailyGoalRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.daily_goal import DailyGoal
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM


class SQLAlchemyDailyGoalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_user(self, user_id: int) -> list[DailyGoal]:
        rows = (
            await self._session.execute(
                select(DailyGoalORM)
                .where(DailyGoalORM.user_id == user_id)
                .order_by(DailyGoalORM.effective_date)
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
