"""Concrete ``DailyGoalRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.daily_goal import DailyGoal
from src.domain.exceptions import DailyGoalConflictException
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM
from src.infrastructure.db.repositories.idempotency import create_idempotent


class SQLAlchemyDailyGoalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, goal: DailyGoal) -> DailyGoal:
        # daily_goals has a second unique constraint (user_id, effective_date)
        # beyond client_id's — create_idempotent only resolves a client_id
        # repeat, so a genuinely different create for a day that already has
        # a goal re-raises IntegrityError here rather than surfacing as a 500.
        try:
            row = await create_idempotent(
                self._session, DailyGoalORM.from_domain(goal), DailyGoalORM
            )
        except IntegrityError as exc:
            raise DailyGoalConflictException(
                f"a daily goal already exists for {goal.effective_date}"
            ) from exc
        return row.to_domain()

    async def list_by_user(self, user_id: int) -> list[DailyGoal]:
        rows = (
            await self._session.execute(
                select(DailyGoalORM)
                .where(DailyGoalORM.user_id == user_id)
                .order_by(DailyGoalORM.effective_date)
            )
        ).scalars().all()
        return [row.to_domain() for row in rows]
