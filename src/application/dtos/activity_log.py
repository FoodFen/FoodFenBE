"""Activity log DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.domain.entities.activity_log import ActivityLog
from src.domain.enums import ActivitySource


@dataclass(frozen=True)
class ActivityLogOutputDTO:
    id: UUID
    user_id: int
    activity_type: str
    calories_burned: int
    source: ActivitySource
    logged_at: datetime
    logged_on: date

    @classmethod
    def from_entity(cls, log: ActivityLog) -> ActivityLogOutputDTO:
        return cls(
            id=log.id,
            user_id=log.user_id,
            activity_type=log.activity_type,
            calories_burned=log.calories_burned,
            source=log.source,
            logged_at=log.logged_at,
            logged_on=log.logged_on,
        )


@dataclass(frozen=True)
class CreateActivityLogInputDTO:
    user_id: int
    activity_type: str
    calories_burned: int
    client_id: str
    source: ActivitySource = ActivitySource.MANUAL
    logged_at: datetime | None = None
    logged_on: date | None = None


@dataclass(frozen=True)
class UpdateActivityLogInputDTO:
    activity_type: str
    calories_burned: int
    source: ActivitySource = ActivitySource.MANUAL
    logged_at: datetime | None = None
    logged_on: date | None = None
