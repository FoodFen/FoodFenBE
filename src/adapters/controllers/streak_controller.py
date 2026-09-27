"""Streak endpoint. HTTP <-> application DTO translation only."""

from __future__ import annotations

from fastapi import APIRouter

from src.adapters.schemas.streak_schemas import StreakResponse, UpsertStreakRequest
from src.application.dtos.streak import UpsertStreakInputDTO
from src.infrastructure.di import CurrentUserDep, UpsertStreakUseCaseDep

router = APIRouter(prefix="/streak", tags=["streak"])


@router.post("", response_model=StreakResponse)
async def upsert_streak(
    body: UpsertStreakRequest, user: CurrentUserDep, use_case: UpsertStreakUseCaseDep
) -> StreakResponse:
    input_dto = UpsertStreakInputDTO(
        user_id=user.id,
        current_streak=body.current_streak,
        longest_streak=body.longest_streak,
        last_active_date=body.last_active_date,
    )
    result = await use_case.execute(input_dto)
    return StreakResponse.from_dto(result)
