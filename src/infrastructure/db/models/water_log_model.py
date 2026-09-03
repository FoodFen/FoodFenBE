"""ORM model for water logs."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.water_log import WaterLog
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey


class WaterLogORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "water_logs"
    __table_args__ = (Index("ix_water_logs_user_logged_at", "user_id", "logged_at"),)

    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_domain(self) -> WaterLog:
        return WaterLog(
            id=self.id,
            user_id=self.user_id,
            amount_ml=self.amount_ml,
            logged_at=self.logged_at,
        )

    @staticmethod
    def from_domain(log: WaterLog) -> WaterLogORM:
        return WaterLogORM(
            id=log.id,
            user_id=log.user_id,
            amount_ml=log.amount_ml,
            logged_at=log.logged_at,
        )
