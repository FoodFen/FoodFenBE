"""Concrete ``DailyGoalRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.daily_goal import DailyGoal
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyDailyGoalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, goal: DailyGoal) -> DailyGoal:
        row = await create_idempotent(self._session, DailyGoalORM.from_domain(goal), DailyGoalORM)
        return row.to_domain()

    async def list_by_user(self, user_id: int) -> list[DailyGoal]:
        rows = (
            await self._session.execute(select(DailyGoalORM).where(DailyGoalORM.user_id == user_id))
        ).scalars().all()
        return [row.to_domain() for row in rows]
