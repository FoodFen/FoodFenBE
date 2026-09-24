"""ListDailyGoalsUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

from src.application.use_cases.list_daily_goals import ListDailyGoalsUseCase
from src.domain.entities.daily_goal import DailyGoal


class FakeDailyGoalRepo:
    def __init__(self, goals: list[DailyGoal] | None = None) -> None:
        self._goals = goals or []

    async def list_by_user(self, user_id: int) -> list[DailyGoal]:
        return [g for g in self._goals if g.user_id == user_id]


async def test_returns_empty_list_when_user_has_no_goals():
    use_case = ListDailyGoalsUseCase(daily_goals=FakeDailyGoalRepo())
    assert await use_case.execute(1) == []


async def test_returns_dtos_for_the_users_goals():
    goal = DailyGoal.create(1, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1))
    other_users_goal = DailyGoal.create(2, 1800, 180.0, 120.0, 50.0, 2000, date(2026, 1, 1))
    use_case = ListDailyGoalsUseCase(daily_goals=FakeDailyGoalRepo([goal, other_users_goal]))

    result = await use_case.execute(1)

    assert len(result) == 1
    assert result[0].target_kcal == 2000
    assert result[0].effective_date == date(2026, 1, 1)
