"""Use case: list every daily goal ever set for the account (append-only, all history)."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.daily_goal import DailyGoalOutputDTO
from src.application.ports.daily_goal_repository import DailyGoalRepositoryProtocol


@dataclass
class ListDailyGoalsUseCase:
    daily_goals: DailyGoalRepositoryProtocol

    async def execute(self, user_id: int) -> list[DailyGoalOutputDTO]:
        goals = await self.daily_goals.list_by_user(user_id)
        return [DailyGoalOutputDTO.from_entity(g) for g in goals]
