"""Plain-Python DTOs crossing the application boundary. Standard library only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.domain.entities.user import User
from src.domain.enums import (
    ActivityLevel,
    CalorieCalcMode,
    CalorieLeftMode,
    DietType,
    Gender,
    SubscriptionTier,
    UnitSystem,
)


@dataclass(frozen=True)
class UserOutputDTO:
    """Mirrors the API contract's ``User`` shape — see docs/authentication.md."""

    id: int
    email: str
    name: str | None
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
    weekly_rate_kg: float | None
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> UserOutputDTO:
        assert user.id is not None, "UserOutputDTO requires a persisted user"
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            gender=user.gender,
            birth_year=user.birth_year,
            unit_system=user.unit_system,
            height=user.height,
            weight_current=user.weight_current,
            weight_goal=user.weight_goal,
            activity_level=user.activity_level,
            diet_type=user.diet_type,
            calorie_calc_mode=user.calorie_calc_mode,
            calorie_left_mode=user.calorie_left_mode,
            subscription_tier=user.subscription_tier,
            weekly_rate_kg=user.weekly_rate_kg,
            created_at=user.created_at,
        )
