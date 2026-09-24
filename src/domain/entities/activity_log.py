"""ActivityLog entity — one exercise session, manual or synced from a health app."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.enums import ActivitySource
from src.domain.validation import require_non_empty, require_non_negative


@dataclass
class ActivityLog:
    id: UUID
    user_id: int
    activity_type: str
    calories_burned: int
    source: ActivitySource = ActivitySource.MANUAL
    logged_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logged_on: date = field(default_factory=lambda: datetime.now(UTC).date())

    def __post_init__(self) -> None:
        self.activity_type = require_non_empty(self.activity_type, "activity_type")
        require_non_negative(self.calories_burned, "calories_burned")

    @classmethod
    def create(
        cls,
        user_id: int,
        activity_type: str,
        calories_burned: int,
        source: ActivitySource = ActivitySource.MANUAL,
        logged_on: date | None = None,
    ) -> ActivityLog:
        logged_at = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            activity_type=activity_type,
            calories_burned=calories_burned,
            source=source,
            logged_at=logged_at,
            logged_on=logged_on or logged_at.date(),
        )
