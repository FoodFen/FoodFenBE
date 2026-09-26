"""Concrete ``DailyGoalRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.daily_goal import DailyGoal
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM


class SQLAlchemyDailyGoalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, goal: DailyGoal) -> DailyGoal:
        # One row per (user_id, effective_date) — changing today's target
        # again replaces that row rather than erroring or creating a second
        # row for the same day (CLAUDE.md's actual invariant only protects a
        # *past* day's row from being rewritten, not today's from changing).
        # Try the insert first (SAVEPOINT-isolated) and fall back to an
        # update on conflict, rather than a check-then-insert race.
        row = DailyGoalORM.from_domain(goal)
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError:
            existing = await self._session.execute(
                select(DailyGoalORM).where(
                    DailyGoalORM.user_id == goal.user_id,
                    DailyGoalORM.effective_date == goal.effective_date,
                )
            )
            found = existing.scalar_one_or_none()
            if found is None:
                raise
            for column in DailyGoalORM.__table__.columns.keys():
                if column != "id":
                    setattr(found, column, getattr(row, column))
            await self._session.flush()
            row = found
        await self._session.refresh(row)
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
