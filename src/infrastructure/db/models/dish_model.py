"""ORM model for dishes. Nutrition columns are typed exactly like food_entries."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.dish import Dish
from src.domain.enums import ModerationStatus
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class DishORM(UUIDPrimaryKey, Base):
    __tablename__ = "dishes"

    restaurant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False)  # VND
    serving_g: Mapped[int] = mapped_column(Integer, nullable=False)
    kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    fiber_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[ModerationStatus] = mapped_column(
        enum_column(ModerationStatus, "moderation_status"), nullable=False, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_domain(self) -> Dish:
        return Dish(
            id=self.id, restaurant_id=self.restaurant_id, name=self.name,
            description=self.description, image_url=self.image_url, price=self.price,
            serving_g=self.serving_g, kcal=self.kcal, protein_g=self.protein_g,
            carbs_g=self.carbs_g, fat_g=self.fat_g, fiber_g=self.fiber_g, status=self.status,
            rejection_reason=self.rejection_reason, created_at=self.created_at,
            updated_at=self.updated_at, reviewed_at=self.reviewed_at,
        )

    @staticmethod
    def from_domain(d: Dish) -> DishORM:
        return DishORM(
            id=d.id, restaurant_id=d.restaurant_id, name=d.name, description=d.description,
            image_url=d.image_url, price=d.price, serving_g=d.serving_g, kcal=d.kcal,
            protein_g=d.protein_g, carbs_g=d.carbs_g, fat_g=d.fat_g, fiber_g=d.fiber_g,
            status=d.status, rejection_reason=d.rejection_reason, created_at=d.created_at,
            updated_at=d.updated_at, reviewed_at=d.reviewed_at,
        )
