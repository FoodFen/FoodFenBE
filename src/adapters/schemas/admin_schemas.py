"""HTTP wire models for /admin."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, ValidationInfo, field_validator

from src.adapters.schemas.base import CamelModel
from src.adapters.schemas.restaurant_schemas import DishResponse, RestaurantResponse
from src.application.dtos.admin import AdminRestaurantDetailDTO, AdminRestaurantRowDTO
from src.domain.enums import ModerationStatus, ReviewDecision


class ReviewRequest(CamelModel):
    decision: ReviewDecision
    # validate_default so an omitted reason is still checked; the error lands on errors.reason.
    reason: str | None = Field(default=None, max_length=1000, validate_default=True)

    @field_validator("reason")
    @classmethod
    def reason_required_to_reject(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("decision") == ReviewDecision.REJECTED and not (value or "").strip():
            raise ValueError("a reason is required to reject")
        return value


class AdminRestaurantRowResponse(CamelModel):
    id: UUID
    name: str
    status: ModerationStatus
    owner_name: str | None
    owner_email: str
    dish_count: int
    pending_dish_count: int
    updated_at: datetime
    rejection_reason: str | None

    @classmethod
    def from_dto(cls, dto: AdminRestaurantRowDTO) -> AdminRestaurantRowResponse:
        return cls(**vars(dto))


class AdminRestaurantDetailResponse(CamelModel):
    restaurant: RestaurantResponse
    dishes: list[DishResponse]

    @classmethod
    def from_dto(cls, dto: AdminRestaurantDetailDTO) -> AdminRestaurantDetailResponse:
        return cls(
            restaurant=RestaurantResponse.from_dto(dto.restaurant),
            dishes=[DishResponse.from_dto(d) for d in dto.dishes],
        )
