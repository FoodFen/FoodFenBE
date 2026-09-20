"""SQLAlchemy ORM model for users — a separate class from the domain entity.

Mapping between the two is explicit: ``to_domain`` / ``from_domain``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

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
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import IntPrimaryKey
from src.infrastructure.db.types import enum_column


class UserORM(IntPrimaryKey, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    gender: Mapped[Gender | None] = mapped_column(enum_column(Gender, "gender"), nullable=True)
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_system: Mapped[UnitSystem] = mapped_column(
        enum_column(UnitSystem, "unit_system"),
        nullable=False,
        server_default=UnitSystem.METRIC.value,
    )
    height: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_current: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_goal: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_level: Mapped[ActivityLevel | None] = mapped_column(
        enum_column(ActivityLevel, "activity_level"), nullable=True
    )
    diet_type: Mapped[DietType | None] = mapped_column(
        enum_column(DietType, "diet_type"), nullable=True
    )
    calorie_calc_mode: Mapped[CalorieCalcMode] = mapped_column(
        enum_column(CalorieCalcMode, "calorie_calc_mode"),
        nullable=False,
        server_default=CalorieCalcMode.AUTO.value,
    )
    calorie_left_mode: Mapped[CalorieLeftMode | None] = mapped_column(
        enum_column(CalorieLeftMode, "calorie_left_mode"), nullable=True
    )
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        enum_column(SubscriptionTier, "subscription_tier"),
        nullable=False,
        server_default=SubscriptionTier.FREE.value,
    )
    weekly_rate_kg: Mapped[float | None] = mapped_column(Float, nullable=True)

    def to_domain(self) -> User:
        return User(
            id=self.id,
            email=self.email,
            name=self.name,
            is_active=self.is_active,
            created_at=self.created_at,
            password_hash=self.password_hash,
            email_verified_at=self.email_verified_at,
            gender=self.gender,
            birth_year=self.birth_year,
            unit_system=self.unit_system,
            height=self.height,
            weight_current=self.weight_current,
            weight_goal=self.weight_goal,
            activity_level=self.activity_level,
            diet_type=self.diet_type,
            calorie_calc_mode=self.calorie_calc_mode,
            calorie_left_mode=self.calorie_left_mode,
            subscription_tier=self.subscription_tier,
            weekly_rate_kg=self.weekly_rate_kg,
        )

    @staticmethod
    def from_domain(user: User) -> UserORM:
        row = UserORM(
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            created_at=user.created_at,
            password_hash=user.password_hash,
            email_verified_at=user.email_verified_at,
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
        )
        # Autoincrement PK: only set it when the entity already has one (an
        # update), never on insert — leave it unset so Postgres assigns it.
        if user.id is not None:
            row.id = user.id
        return row
