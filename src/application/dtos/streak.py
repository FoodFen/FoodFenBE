"""Streak DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from src.domain.entities.streak import Streak


@dataclass(frozen=True)
class StreakOutputDTO:
    id: UUID
    user_id: int
    current_streak: int
    longest_streak: int
    last_active_date: date | None

    @classmethod
    def from_entity(cls, streak: Streak) -> StreakOutputDTO:
        return cls(
            id=streak.id,
            user_id=streak.user_id,
            current_streak=streak.current_streak,
            longest_streak=streak.longest_streak,
            last_active_date=streak.last_active_date,
        )


@dataclass(frozen=True)
class UpsertStreakInputDTO:
    user_id: int
    current_streak: int
    longest_streak: int
    last_active_date: date | None
