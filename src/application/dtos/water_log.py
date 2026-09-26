"""Water log DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.domain.entities.water_log import WaterLog


@dataclass(frozen=True)
class WaterLogOutputDTO:
    id: UUID
    user_id: int
    amount_ml: int
    logged_at: datetime
    logged_on: date

    @classmethod
    def from_entity(cls, log: WaterLog) -> WaterLogOutputDTO:
        return cls(
            id=log.id,
            user_id=log.user_id,
            amount_ml=log.amount_ml,
            logged_at=log.logged_at,
            logged_on=log.logged_on,
        )


@dataclass(frozen=True)
class CreateWaterLogInputDTO:
    user_id: int
    amount_ml: int
    client_id: str
    logged_at: datetime | None = None
    logged_on: date | None = None


@dataclass(frozen=True)
class UpdateWaterLogInputDTO:
    amount_ml: int
    logged_at: datetime | None = None
    logged_on: date | None = None
