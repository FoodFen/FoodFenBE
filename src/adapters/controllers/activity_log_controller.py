"""Activity log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from src.adapters.schemas.activity_log_schemas import (
    ActivityLogResponse,
    CreateActivityLogRequest,
    UpdateActivityLogRequest,
)
from src.application.dtos.activity_log import CreateActivityLogInputDTO, UpdateActivityLogInputDTO
from src.infrastructure.di import (
    CreateActivityLogUseCaseDep,
    CurrentUserDep,
    ListActivityLogsUseCaseDep,
    UpdateActivityLogUseCaseDep,
)

router = APIRouter(prefix="/activity-logs", tags=["activity-logs"])


@router.post("", response_model=ActivityLogResponse)
async def create_activity_log(
    body: CreateActivityLogRequest, user: CurrentUserDep, use_case: CreateActivityLogUseCaseDep
) -> ActivityLogResponse:
    input_dto = CreateActivityLogInputDTO(
        user_id=user.id,
        activity_type=body.activity_type,
        calories_burned=body.calories_burned,
        client_id=body.client_id,
        source=body.source,
        logged_on=body.logged_on,
    )
    result = await use_case.execute(input_dto)
    return ActivityLogResponse.from_dto(result)


@router.get("", response_model=list[ActivityLogResponse])
async def list_activity_logs(
    user: CurrentUserDep,
    use_case: ListActivityLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[ActivityLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [ActivityLogResponse.from_dto(dto) for dto in result]


@router.patch("/{log_id}", response_model=ActivityLogResponse)
async def update_activity_log(
    log_id: UUID,
    body: UpdateActivityLogRequest,
    user: CurrentUserDep,
    use_case: UpdateActivityLogUseCaseDep,
) -> ActivityLogResponse:
    input_dto = UpdateActivityLogInputDTO(
        activity_type=body.activity_type,
        calories_burned=body.calories_burned,
        source=body.source,
        logged_on=body.logged_on,
    )
    result = await use_case.execute(user_id=user.id, log_id=log_id, input_dto=input_dto)
    return ActivityLogResponse.from_dto(result)
