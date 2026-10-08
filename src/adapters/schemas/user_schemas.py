"""HTTP wire model for the ``User`` shape in the front-end API contract.

Field names are camelCase over the wire (``CamelModel``); ``display_name`` is
the one field whose Python name doesn't just camel-case from the domain's
name for it (``User.name``), so ``from_dto`` maps explicitly rather than
relying on ``from_attributes``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from src.adapters.schemas.base import CamelModel
from src.application.dtos.user import MeOutputDTO, UserOutputDTO
from src.domain.enums import (
    ActivityLevel,
    CalorieCalcMode,
    CalorieLeftMode,
    DietType,
    Gender,
    SubscriptionTier,
    UnitSystem,
    UserRole,
)


class UserResponse(CamelModel):
    id: int
    email: str
    display_name: str | None
    gender: Gender | None
    birth_year: int | None
    unit_system: UnitSystem
    height: float | None
    weight_current: float | None
    weight_goal: float | None
    activity_level: ActivityLevel | None
    diet_type: DietType | None
    calorie_calc_mode: CalorieCalcMode
    calorie_left_mode: CalorieLeftMode | None
    subscription_tier: SubscriptionTier
    role: UserRole
    weekly_rate_kg: float | None
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: UserOutputDTO) -> UserResponse:
        return cls(
            id=dto.id,
            email=dto.email,
            display_name=dto.name,
            gender=dto.gender,
            birth_year=dto.birth_year,
            unit_system=dto.unit_system,
            height=dto.height,
            weight_current=dto.weight_current,
            weight_goal=dto.weight_goal,
            activity_level=dto.activity_level,
            diet_type=dto.diet_type,
            calorie_calc_mode=dto.calorie_calc_mode,
            calorie_left_mode=dto.calorie_left_mode,
            subscription_tier=dto.subscription_tier,
            role=dto.role,
            weekly_rate_kg=dto.weekly_rate_kg,
            created_at=dto.created_at,
        )


class MeResponse(UserResponse):
    """``GET /auth/me`` only: ``restaurantId`` costs a lookup the session payloads don't need."""

    restaurant_id: UUID | None

    @classmethod
    def from_me(cls, dto: MeOutputDTO) -> MeResponse:
        return cls(**UserResponse.from_dto(dto.user).model_dump(), restaurant_id=dto.restaurant_id)


class UpdateUserProfileRequest(CamelModel):
    """Partial patch — every field optional; omitted fields are left
    unchanged. ``extra="forbid"`` (overriding ``CamelModel``'s default)
    rejects ``id``/``createdAt``/``subscriptionTier`` in the body outright,
    rather than silently ignoring an attempt to self-grant Premium."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    email: str | None = None
    display_name: str | None = None
    gender: Gender | None = None
    birth_year: int | None = None
    unit_system: UnitSystem | None = None
    height: float | None = None
    weight_current: float | None = None
    weight_goal: float | None = None
    activity_level: ActivityLevel | None = None
    diet_type: DietType | None = None
    calorie_calc_mode: CalorieCalcMode | None = None
    calorie_left_mode: CalorieLeftMode | None = None
    weekly_rate_kg: float | None = None
