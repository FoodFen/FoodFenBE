"""Daily goal endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter

from src.adapters.schemas.daily_goal_schemas import CreateDailyGoalRequest, DailyGoalResponse
from src.application.dtos.daily_goal import CreateDailyGoalInputDTO
from src.infrastructure.di import CreateDailyGoalUseCaseDep, CurrentUserDep, ListDailyGoalsUseCaseDep

router = APIRouter(prefix="/daily-goals", tags=["daily-goals"])


@router.post("", response_model=DailyGoalResponse)
async def create_daily_goal(
    body: CreateDailyGoalRequest, user: CurrentUserDep, use_case: CreateDailyGoalUseCaseDep
) -> DailyGoalResponse:
    input_dto = CreateDailyGoalInputDTO(
        user_id=user.id,
        target_kcal=body.target_kcal,
        target_carbs_g=body.target_carbs_g,
        target_protein_g=body.target_protein_g,
        target_fat_g=body.target_fat_g,
        target_water_ml=body.target_water_ml,
        effective_date=body.effective_date,
        client_id=body.client_id,
    )
    result = await use_case.execute(input_dto)
    return DailyGoalResponse.from_dto(result)


@router.get("", response_model=list[DailyGoalResponse])
async def list_daily_goals(
    user: CurrentUserDep, use_case: ListDailyGoalsUseCaseDep
) -> list[DailyGoalResponse]:
    result = await use_case.execute(user.id)
    return [DailyGoalResponse.from_dto(dto) for dto in result]
