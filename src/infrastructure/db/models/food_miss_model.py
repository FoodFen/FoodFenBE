"""ORM model for the AI's unmatched food names (one row per folded name)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.food_miss import FoodMiss
from src.domain.enums import FoodMissStatus
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class FoodMissORM(UUIDPrimaryKey, Base):
    __tablename__ = "food_misses"
    __table_args__ = (
        CheckConstraint("(status = 'resolved') = (resolved_food_id IS NOT NULL)", name="resolved_food"),
    )

    key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[FoodMissStatus] = mapped_column(enum_column(FoodMissStatus, "food_miss_status"), nullable=False)
    resolved_food_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("foods.id"), nullable=True)

    def to_domain(self) -> FoodMiss:
        return FoodMiss(
            self.id, self.key, self.name, self.language, self.count, self.first_seen_at, self.last_seen_at,
            self.status, self.resolved_food_id,
        )
