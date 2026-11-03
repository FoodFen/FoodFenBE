"""ORM model for the append-only catalog audit log."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.food_change import FoodChange
from src.domain.enums import FoodChangeAction
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class FoodChangeORM(UUIDPrimaryKey, Base):
    __tablename__ = "food_changes"

    food_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("foods.id"), nullable=False, index=True)
    admin_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[FoodChangeAction] = mapped_column(enum_column(FoodChangeAction, "food_change_action"), nullable=False)
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, c: FoodChange) -> FoodChangeORM:
        return cls(
            id=c.id, food_id=c.food_id, admin_id=c.admin_id, action=c.action, before=c.before, after=c.after,
            created_at=c.created_at,
        )

    def to_domain(self) -> FoodChange:
        return FoodChange(self.id, self.food_id, self.admin_id, self.action, self.before, self.after, self.created_at)
