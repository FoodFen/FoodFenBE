"""ORM model for paid-placement packages (N days for a whole restaurant)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, func, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.ad_package import AdPackage
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey


class AdPackageORM(UUIDPrimaryKey, Base):
    __tablename__ = "ad_packages"

    days: Mapped[int] = mapped_column(Integer, nullable=False)
    price_vnd: Mapped[Decimal] = mapped_column(Numeric(12, 0), nullable=False)  # VND has no minor unit
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def to_domain(self) -> AdPackage:
        return AdPackage(
            id=self.id, days=self.days, price_vnd=self.price_vnd, active=self.active, created_at=self.created_at
        )

    @staticmethod
    def from_domain(p: AdPackage) -> AdPackageORM:
        return AdPackageORM(id=p.id, days=p.days, price_vnd=p.price_vnd, active=p.active, created_at=p.created_at)
