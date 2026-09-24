"""HTTP wire models for the water logs API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.application.dtos.water_log import WaterLogOutputDTO


class WaterLogResponse(CamelModel):
    id: UUID
    user_id: int
    amount_ml: int
    logged_at: datetime
    logged_on: date

    @classmethod
    def from_dto(cls, dto: WaterLogOutputDTO) -> WaterLogResponse:
        return cls(
            id=dto.id,
            user_id=dto.user_id,
            amount_ml=dto.amount_ml,
            logged_at=dto.logged_at,
            logged_on=dto.logged_on,
        )


class CreateWaterLogRequest(CamelModel):
    amount_ml: int
    client_id: str = Field(min_length=1)
    logged_on: date | None = None
