"""ORM model for nutrition tips (bilingual one-liners the app shows while loading)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.nutrition_tip import NutritionTip
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey


class NutritionTipORM(UUIDPrimaryKey, Base):
    __tablename__ = "nutrition_tips"

    text_vi: Mapped[str] = mapped_column(Text, nullable=False)
    text_en: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_domain(self) -> NutritionTip:
        return NutritionTip(
            id=self.id, text_vi=self.text_vi, text_en=self.text_en, is_active=self.is_active,
            created_at=self.created_at, updated_at=self.updated_at,
        )

    @staticmethod
    def from_domain(t: NutritionTip) -> NutritionTipORM:
        return NutritionTipORM(
            id=t.id, text_vi=t.text_vi, text_en=t.text_en, is_active=t.is_active,
            created_at=t.created_at, updated_at=t.updated_at,
        )
