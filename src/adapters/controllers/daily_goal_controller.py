"""Daily goal endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter

from src.adapters.schemas.daily_goal_schemas import DailyGoalResponse
from src.infrastructure.di import CurrentUserDep, ListDailyGoalsUseCaseDep

router = APIRouter(prefix="/daily-goals", tags=["daily-goals"])


@router.get("", response_model=list[DailyGoalResponse])
async def list_daily_goals(
    user: CurrentUserDep, use_case: ListDailyGoalsUseCaseDep
) -> list[DailyGoalResponse]:
    result = await use_case.execute(user.id)
    return [DailyGoalResponse.from_dto(dto) for dto in result]
