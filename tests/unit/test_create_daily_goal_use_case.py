"""CreateDailyGoalUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

from src.application.dtos.daily_goal import CreateDailyGoalInputDTO
from src.application.use_cases.create_daily_goal import CreateDailyGoalUseCase
from src.domain.entities.daily_goal import DailyGoal


class FakeDailyGoalRepo:
    def __init__(self) -> None:
        self._by_client_id: dict = {}

    async def create(self, goal: DailyGoal) -> DailyGoal:
        key = (goal.user_id, goal.client_id)
        if key in self._by_client_id:
            return self._by_client_id[key]
        self._by_client_id[key] = goal
        return goal

    async def list_by_user(self, user_id):
        return [g for g in self._by_client_id.values() if g.user_id == user_id]


def _dto(client_id="goal_1") -> CreateDailyGoalInputDTO:
    return CreateDailyGoalInputDTO(
        user_id=1,
        target_kcal=2000,
        target_carbs_g=200.0,
        target_protein_g=150.0,
        target_fat_g=60.0,
        target_water_ml=2500,
        effective_date=date(2026, 1, 1),
        client_id=client_id,
    )


async def test_create_returns_dto():
    use_case = CreateDailyGoalUseCase(daily_goals=FakeDailyGoalRepo())
    result = await use_case.execute(_dto())
    assert result.target_kcal == 2000
    assert result.effective_date == date(2026, 1, 1)


async def test_create_with_repeated_client_id_returns_the_same_goal():
    repo = FakeDailyGoalRepo()
    use_case = CreateDailyGoalUseCase(daily_goals=repo)
    first = await use_case.execute(_dto())
    second = await use_case.execute(_dto())
    assert second.id == first.id
