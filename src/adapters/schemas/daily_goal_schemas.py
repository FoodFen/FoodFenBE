"""HTTP wire models for the daily goals API."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.application.dtos.daily_goal import DailyGoalOutputDTO


class DailyGoalResponse(CamelModel):
    id: UUID
    user_id: int
    target_kcal: int
    target_carbs_g: float
    target_protein_g: float
    target_fat_g: float
    target_water_ml: int
    effective_date: date

    @classmethod
    def from_dto(cls, dto: DailyGoalOutputDTO) -> DailyGoalResponse:
        return cls(
            id=dto.id,
            user_id=dto.user_id,
            target_kcal=dto.target_kcal,
            target_carbs_g=dto.target_carbs_g,
            target_protein_g=dto.target_protein_g,
            target_fat_g=dto.target_fat_g,
            target_water_ml=dto.target_water_ml,
            effective_date=dto.effective_date,
        )


class CreateDailyGoalRequest(CamelModel):
    target_kcal: int
    target_carbs_g: float
    target_protein_g: float
    target_fat_g: float
    target_water_ml: int
    effective_date: date
    client_id: str = Field(min_length=1)
