"""WeightLog entity — one weigh-in."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.validation import require_non_empty, require_positive


@dataclass
class WeightLog:
    id: UUID
    user_id: int
    weight: float
    recorded_at: date
    client_id: str

    def __post_init__(self) -> None:
        require_positive(self.weight, "weight")
        self.client_id = require_non_empty(self.client_id, "client_id")

    @classmethod
    def create(
        cls, user_id: int, weight: float, recorded_at: date | None = None, *, client_id: str
    ) -> WeightLog:
        return cls(
            id=uuid4(),
            user_id=user_id,
            weight=weight,
            recorded_at=recorded_at or datetime.now(UTC).date(),
            client_id=client_id,
        )
