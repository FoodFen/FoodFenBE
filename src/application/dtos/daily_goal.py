"""Daily goal DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from src.domain.entities.daily_goal import DailyGoal


@dataclass(frozen=True)
class DailyGoalOutputDTO:
    id: UUID
    user_id: int
    target_kcal: int
    target_carbs_g: float
    target_protein_g: float
    target_fat_g: float
    target_water_ml: int
    effective_date: date

    @classmethod
    def from_entity(cls, goal: DailyGoal) -> DailyGoalOutputDTO:
        return cls(
            id=goal.id,
            user_id=goal.user_id,
            target_kcal=goal.target_kcal,
            target_carbs_g=goal.target_carbs_g,
            target_protein_g=goal.target_protein_g,
            target_fat_g=goal.target_fat_g,
            target_water_ml=goal.target_water_ml,
            effective_date=goal.effective_date,
        )


@dataclass(frozen=True)
class CreateDailyGoalInputDTO:
    user_id: int
    target_kcal: int
    target_carbs_g: float
    target_protein_g: float
    target_fat_g: float
    target_water_ml: int
    effective_date: date
    client_id: str
