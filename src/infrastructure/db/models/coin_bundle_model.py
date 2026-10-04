"""ORM model for the coin-redeemable Premium bundles (price list, edited with SQL)."""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.coin_bundle import CoinBundle
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey


class CoinBundleORM(UUIDPrimaryKey, Base):
    __tablename__ = "coin_bundles"
    # Redeem looks a bundle up by `days`, so two rows may not offer the same length.
    __table_args__ = (UniqueConstraint("days", name="uq_coin_bundles_days"),)

    days: Mapped[int] = mapped_column(Integer, nullable=False)
    coin_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    def to_domain(self) -> CoinBundle:
        return CoinBundle(id=self.id, days=self.days, coin_cost=self.coin_cost)
