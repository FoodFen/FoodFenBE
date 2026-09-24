"""ORM model for weight logs."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.weight_log import WeightLog
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey


class WeightLogORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "weight_logs"
    __table_args__ = (
        Index("ix_weight_logs_user_recorded_at", "user_id", "recorded_at"),
        UniqueConstraint("user_id", "client_id", name="uq_weight_logs_client_id"),
    )

    weight: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[date] = mapped_column(Date, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)

    def to_domain(self) -> WeightLog:
        return WeightLog(
            id=self.id,
            user_id=self.user_id,
            weight=self.weight,
            recorded_at=self.recorded_at,
            client_id=self.client_id,
        )

    @staticmethod
    def from_domain(log: WeightLog) -> WeightLogORM:
        return WeightLogORM(
            id=log.id,
            user_id=log.user_id,
            weight=log.weight,
            recorded_at=log.recorded_at,
            client_id=log.client_id,
        )
