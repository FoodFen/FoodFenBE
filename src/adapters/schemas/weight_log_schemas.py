"""HTTP wire models for the weight logs API."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.application.dtos.weight_log import WeightLogOutputDTO


class WeightLogResponse(CamelModel):
    id: UUID
    user_id: int
    weight: float
    recorded_at: date

    @classmethod
    def from_dto(cls, dto: WeightLogOutputDTO) -> WeightLogResponse:
        return cls(id=dto.id, user_id=dto.user_id, weight=dto.weight, recorded_at=dto.recorded_at)


class CreateWeightLogRequest(CamelModel):
    weight: float
    client_id: str = Field(min_length=1)
    recorded_at: date | None = None
