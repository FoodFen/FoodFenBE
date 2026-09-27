"""UpsertStreakUseCase — unit tests against an in-memory fake repository."""

from __future__ import annotations

from datetime import date

from src.application.dtos.streak import UpsertStreakInputDTO
from src.application.use_cases.upsert_streak import UpsertStreakUseCase
from src.domain.entities.streak import Streak


class FakeStreakRepository:
    def __init__(self) -> None:
        self._by_user: dict[int, Streak] = {}

    async def upsert(self, streak: Streak) -> Streak:
        existing = self._by_user.get(streak.user_id)
        if existing is not None:
            streak.id = existing.id
        self._by_user[streak.user_id] = streak
        return streak


async def test_first_push_creates_the_row():
    use_case = UpsertStreakUseCase(streaks=FakeStreakRepository())

    result = await use_case.execute(
        UpsertStreakInputDTO(
            user_id=1, current_streak=3, longest_streak=5, last_active_date=date(2026, 1, 15)
        )
    )

    assert result.current_streak == 3
    assert result.longest_streak == 5
    assert result.last_active_date == date(2026, 1, 15)


async def test_second_push_replaces_the_same_row():
    use_case = UpsertStreakUseCase(streaks=FakeStreakRepository())
    first = await use_case.execute(
        UpsertStreakInputDTO(user_id=1, current_streak=3, longest_streak=5, last_active_date=None)
    )

    second = await use_case.execute(
        UpsertStreakInputDTO(
            user_id=1, current_streak=4, longest_streak=5, last_active_date=date(2026, 1, 16)
        )
    )

    assert second.id == first.id
    assert second.current_streak == 4
