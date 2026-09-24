"""ORM model for water logs."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.water_log import WaterLog
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey


class WaterLogORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "water_logs"
    __table_args__ = (
        Index("ix_water_logs_user_logged_at", "user_id", "logged_at"),
        Index("ix_water_logs_user_logged_on", "user_id", "logged_on"),
        UniqueConstraint("user_id", "client_id", name="uq_water_logs_client_id"),
    )

    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    logged_on: Mapped[date] = mapped_column(Date, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_domain(self) -> WaterLog:
        return WaterLog(
            id=self.id,
            user_id=self.user_id,
            amount_ml=self.amount_ml,
            client_id=self.client_id,
            logged_at=self.logged_at,
            logged_on=self.logged_on,
        )

    @staticmethod
    def from_domain(log: WaterLog) -> WaterLogORM:
        return WaterLogORM(
            id=log.id,
            user_id=log.user_id,
            amount_ml=log.amount_ml,
            client_id=log.client_id,
            logged_at=log.logged_at,
            logged_on=log.logged_on,
        )
