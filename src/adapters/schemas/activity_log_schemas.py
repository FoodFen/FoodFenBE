"""HTTP wire models for the activity logs API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from src.adapters.schemas.base import CamelModel
from src.application.dtos.activity_log import ActivityLogOutputDTO
from src.domain.enums import ActivitySource


class ActivityLogResponse(CamelModel):
    id: UUID
    user_id: int
    activity_type: str
    calories_burned: int
    source: ActivitySource
    logged_at: datetime
    logged_on: date

    @classmethod
    def from_dto(cls, dto: ActivityLogOutputDTO) -> ActivityLogResponse:
        return cls(
            id=dto.id,
            user_id=dto.user_id,
            activity_type=dto.activity_type,
            calories_burned=dto.calories_burned,
            source=dto.source,
            logged_at=dto.logged_at,
            logged_on=dto.logged_on,
        )
