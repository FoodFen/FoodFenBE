"""Use case: push the caller's one streak row (POST /streak).

A singleton per user — there is no separate create/update split. Ownership
is implicit from the authenticated user, and a retry with identical values
is already a no-op, so no client_id is needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from src.application.dtos.streak import StreakOutputDTO, UpsertStreakInputDTO
from src.application.ports.streak_repository import StreakRepositoryProtocol
from src.domain.entities.streak import Streak


@dataclass
class UpsertStreakUseCase:
    streaks: StreakRepositoryProtocol

    async def execute(self, input_dto: UpsertStreakInputDTO) -> StreakOutputDTO:
        streak = Streak(
            id=uuid4(),
            user_id=input_dto.user_id,
            current_streak=input_dto.current_streak,
            longest_streak=input_dto.longest_streak,
            last_active_date=input_dto.last_active_date,
        )
        saved = await self.streaks.upsert(streak)
        return StreakOutputDTO.from_entity(saved)
