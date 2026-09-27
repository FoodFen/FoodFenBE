"""HTTP wire models for the streak API."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from src.adapters.schemas.base import CamelModel
from src.application.dtos.streak import StreakOutputDTO


class StreakResponse(CamelModel):
    id: UUID
    user_id: int
    current_streak: int
    longest_streak: int
    last_active_date: date | None

    @classmethod
    def from_dto(cls, dto: StreakOutputDTO) -> StreakResponse:
        return cls(
            id=dto.id,
            user_id=dto.user_id,
            current_streak=dto.current_streak,
            longest_streak=dto.longest_streak,
            last_active_date=dto.last_active_date,
        )


class UpsertStreakRequest(CamelModel):
    current_streak: int
    longest_streak: int
    last_active_date: date | None
