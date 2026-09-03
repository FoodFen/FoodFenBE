"""WeightLog entity — one weigh-in."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.validation import require_positive


@dataclass
class WeightLog:
    id: UUID
    user_id: UUID
    weight: float
    recorded_at: date

    def __post_init__(self) -> None:
        require_positive(self.weight, "weight")

    @classmethod
    def create(cls, user_id: UUID, weight: float, recorded_at: date | None = None) -> WeightLog:
        return cls(
            id=uuid4(),
            user_id=user_id,
            weight=weight,
            recorded_at=recorded_at or datetime.now(UTC).date(),
        )
