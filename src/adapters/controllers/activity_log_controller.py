"""Activity log endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from src.adapters.schemas.activity_log_schemas import ActivityLogResponse
from src.infrastructure.di import CurrentUserDep, ListActivityLogsUseCaseDep

router = APIRouter(prefix="/activity-logs", tags=["activity-logs"])


@router.get("", response_model=list[ActivityLogResponse])
async def list_activity_logs(
    user: CurrentUserDep,
    use_case: ListActivityLogsUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[ActivityLogResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [ActivityLogResponse.from_dto(dto) for dto in result]
