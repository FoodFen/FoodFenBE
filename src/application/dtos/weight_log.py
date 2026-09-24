"""Weight log DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from src.domain.entities.weight_log import WeightLog


@dataclass(frozen=True)
class WeightLogOutputDTO:
    id: UUID
    user_id: int
    weight: float
    recorded_at: date

    @classmethod
    def from_entity(cls, log: WeightLog) -> WeightLogOutputDTO:
        return cls(
            id=log.id,
            user_id=log.user_id,
            weight=log.weight,
            recorded_at=log.recorded_at,
        )
