"""ORM model for streaks — at most one row per user."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.streak import Streak
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey


class StreakORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "streaks"
    # The ERD's USER ||--o| STREAK: zero or one, enforced here rather than trusted.
    __table_args__ = (UniqueConstraint("user_id", name="uq_streaks_user"),)

    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    def to_domain(self) -> Streak:
        return Streak(
            id=self.id,
            user_id=self.user_id,
            current_streak=self.current_streak,
            longest_streak=self.longest_streak,
            last_active_date=self.last_active_date,
        )

    @staticmethod
    def from_domain(streak: Streak) -> StreakORM:
        return StreakORM(
            id=streak.id,
            user_id=streak.user_id,
            current_streak=streak.current_streak,
            longest_streak=streak.longest_streak,
            last_active_date=streak.last_active_date,
        )
