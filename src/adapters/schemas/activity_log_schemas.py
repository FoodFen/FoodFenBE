"""HTTP wire models for the activity logs API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

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


class CreateActivityLogRequest(CamelModel):
    activity_type: str = Field(min_length=1)
    calories_burned: int
    client_id: str = Field(min_length=1)
    source: ActivitySource = ActivitySource.MANUAL
    logged_at: datetime | None = None
    logged_on: date | None = None


class UpdateActivityLogRequest(CamelModel):
    """Full replace, same shape as ``CreateActivityLogRequest`` minus
    ``clientId`` — an omitted ``source`` is not "left unchanged", it resets
    to ``MANUAL`` like every other omitted field on this full-replace PATCH."""

    activity_type: str = Field(min_length=1)
    calories_burned: int
    source: ActivitySource = ActivitySource.MANUAL
    logged_at: datetime | None = None
    logged_on: date | None = None
