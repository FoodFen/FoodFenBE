"""Weight log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from src.adapters.schemas.weight_log_schemas import CreateWeightLogRequest, WeightLogResponse
from src.application.dtos.weight_log import CreateWeightLogInputDTO
from src.infrastructure.di import (
    CreateWeightLogUseCaseDep,
    CurrentUserDep,
    ListWeightLogsUseCaseDep,
)

router = APIRouter(prefix="/weight-logs", tags=["weight-logs"])


@router.post("", response_model=WeightLogResponse)
async def create_weight_log(
    body: CreateWeightLogRequest, user: CurrentUserDep, use_case: CreateWeightLogUseCaseDep
) -> WeightLogResponse:
    input_dto = CreateWeightLogInputDTO(
        user_id=user.id, weight=body.weight, client_id=body.client_id, recorded_at=body.recorded_at
    )
    result = await use_case.execute(input_dto)
    return WeightLogResponse.from_dto(result)


@router.get("", response_model=list[WeightLogResponse])
async def list_weight_logs(
    user: CurrentUserDep,
    use_case: ListWeightLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[WeightLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [WeightLogResponse.from_dto(dto) for dto in result]
