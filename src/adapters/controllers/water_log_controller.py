"""Water log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from src.adapters.schemas.water_log_schemas import (
    CreateWaterLogRequest,
    UpdateWaterLogRequest,
    WaterLogResponse,
)
from src.application.dtos.water_log import CreateWaterLogInputDTO, UpdateWaterLogInputDTO
from src.infrastructure.di import (
    CreateWaterLogUseCaseDep,
    CurrentUserDep,
    DeleteWaterLogUseCaseDep,
    ListWaterLogsUseCaseDep,
    UpdateWaterLogUseCaseDep,
)

router = APIRouter(prefix="/water-logs", tags=["water-logs"])


@router.post("", response_model=WaterLogResponse)
async def create_water_log(
    body: CreateWaterLogRequest, user: CurrentUserDep, use_case: CreateWaterLogUseCaseDep
) -> WaterLogResponse:
    input_dto = CreateWaterLogInputDTO(
        user_id=user.id,
        amount_ml=body.amount_ml,
        client_id=body.client_id,
        logged_at=body.logged_at,
        logged_on=body.logged_on,
    )
    result = await use_case.execute(input_dto)
    return WaterLogResponse.from_dto(result)


@router.get("", response_model=list[WaterLogResponse])
async def list_water_logs(
    user: CurrentUserDep,
    use_case: ListWaterLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[WaterLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [WaterLogResponse.from_dto(dto) for dto in result]


@router.patch("/{log_id}", response_model=WaterLogResponse)
async def update_water_log(
    log_id: UUID,
    body: UpdateWaterLogRequest,
    user: CurrentUserDep,
    use_case: UpdateWaterLogUseCaseDep,
) -> WaterLogResponse:
    input_dto = UpdateWaterLogInputDTO(
        amount_ml=body.amount_ml, logged_at=body.logged_at, logged_on=body.logged_on
    )
    result = await use_case.execute(user_id=user.id, log_id=log_id, input_dto=input_dto)
    return WaterLogResponse.from_dto(result)


@router.delete("/{log_id}", status_code=204)
async def delete_water_log(
    log_id: UUID, user: CurrentUserDep, use_case: DeleteWaterLogUseCaseDep
) -> None:
    await use_case.execute(user_id=user.id, log_id=log_id)
