"""Weight log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from src.adapters.schemas.weight_log_schemas import WeightLogResponse
from src.infrastructure.di import CurrentUserDep, ListWeightLogsUseCaseDep

router = APIRouter(prefix="/weight-logs", tags=["weight-logs"])


@router.get("", response_model=list[WeightLogResponse])
async def list_weight_logs(
    user: CurrentUserDep,
    use_case: ListWeightLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[WeightLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [WeightLogResponse.from_dto(dto) for dto in result]
