"""Use case: set a new daily target. Goals are append-only — never edited or
deleted once created (see DailyGoal's own docstring)."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.daily_goal import CreateDailyGoalInputDTO, DailyGoalOutputDTO
from src.application.ports.daily_goal_repository import DailyGoalRepositoryProtocol
from src.domain.entities.daily_goal import DailyGoal


@dataclass
class CreateDailyGoalUseCase:
    daily_goals: DailyGoalRepositoryProtocol

    async def execute(self, input_dto: CreateDailyGoalInputDTO) -> DailyGoalOutputDTO:
        goal = DailyGoal.create(
            user_id=input_dto.user_id,
            target_kcal=input_dto.target_kcal,
            target_carbs_g=input_dto.target_carbs_g,
            target_protein_g=input_dto.target_protein_g,
            target_fat_g=input_dto.target_fat_g,
            target_water_ml=input_dto.target_water_ml,
            effective_date=input_dto.effective_date,
            client_id=input_dto.client_id,
        )
        created = await self.daily_goals.create(goal)
        return DailyGoalOutputDTO.from_entity(created)
