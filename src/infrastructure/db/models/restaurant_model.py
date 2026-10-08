"""ORM model for restaurants. Separate from the domain entity; explicit mapping."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.restaurant import Restaurant
from src.domain.enums import ModerationStatus
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class RestaurantORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "restaurants"
    # One restaurant per owner: also what turns a concurrent second create into a 409.
    __table_args__ = (UniqueConstraint("user_id", name="uq_restaurants_user_id"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    opening_hours: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[ModerationStatus] = mapped_column(
        enum_column(ModerationStatus, "moderation_status"), nullable=False, index=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_domain(self) -> Restaurant:
        return Restaurant(
            id=self.id, user_id=self.user_id, name=self.name, description=self.description,
            address=self.address, phone=self.phone, opening_hours=self.opening_hours,
            latitude=self.latitude, longitude=self.longitude, image_url=self.image_url,
            status=self.status, rejection_reason=self.rejection_reason,
            created_at=self.created_at, updated_at=self.updated_at, reviewed_at=self.reviewed_at,
        )

    @staticmethod
    def from_domain(r: Restaurant) -> RestaurantORM:
        return RestaurantORM(
            id=r.id, user_id=r.user_id, name=r.name, description=r.description,
            address=r.address, phone=r.phone, opening_hours=r.opening_hours,
            latitude=r.latitude, longitude=r.longitude, image_url=r.image_url,
            status=r.status, rejection_reason=r.rejection_reason,
            created_at=r.created_at, updated_at=r.updated_at, reviewed_at=r.reviewed_at,
        )
