"""ORM model for activity logs."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.activity_log import ActivityLog
from src.domain.enums import ActivitySource
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class ActivityLogORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "activity_logs"
    __table_args__ = (
        Index("ix_activity_logs_user_logged_at", "user_id", "logged_at"),
        Index("ix_activity_logs_user_logged_on", "user_id", "logged_on"),
        UniqueConstraint("user_id", "client_id", name="uq_activity_logs_client_id"),
    )

    activity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    calories_burned: Mapped[int] = mapped_column(Integer, nullable=False)
    client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[ActivitySource] = mapped_column(
        enum_column(ActivitySource, "activity_source"),
        nullable=False,
        server_default=ActivitySource.MANUAL.value,
    )
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    logged_on: Mapped[date] = mapped_column(Date, nullable=False)

    def to_domain(self) -> ActivityLog:
        return ActivityLog(
            id=self.id,
            user_id=self.user_id,
            activity_type=self.activity_type,
            calories_burned=self.calories_burned,
            client_id=self.client_id,
            source=self.source,
            logged_at=self.logged_at,
            logged_on=self.logged_on,
        )

    @staticmethod
    def from_domain(log: ActivityLog) -> ActivityLogORM:
        return ActivityLogORM(
            id=log.id,
            user_id=log.user_id,
            activity_type=log.activity_type,
            calories_burned=log.calories_burned,
            client_id=log.client_id,
            source=log.source,
            logged_at=log.logged_at,
            logged_on=log.logged_on,
        )
