"""Daily count of times a restaurant was shown in the sponsored section (Vietnam day)."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.db.base import Base


class AdImpressionORM(Base):
    __tablename__ = "ad_impressions"

    restaurant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
