"""Water log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from src.adapters.schemas.water_log_schemas import WaterLogResponse
from src.infrastructure.di import CurrentUserDep, ListWaterLogsUseCaseDep

router = APIRouter(prefix="/water-logs", tags=["water-logs"])


@router.get("", response_model=list[WaterLogResponse])
async def list_water_logs(
    user: CurrentUserDep,
    use_case: ListWaterLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[WaterLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [WaterLogResponse.from_dto(dto) for dto in result]
