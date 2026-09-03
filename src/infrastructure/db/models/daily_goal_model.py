"""ORM model for daily goals."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.daily_goal import DailyGoal
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey


class DailyGoalORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "daily_goals"
    # One set of targets per user per day; the history is the sequence of rows.
    __table_args__ = (
        UniqueConstraint("user_id", "effective_date", name="uq_daily_goals_user_date"),
    )

    target_kcal: Mapped[int] = mapped_column(Integer, nullable=False)
    target_carbs_g: Mapped[float] = mapped_column(Float, nullable=False)
    target_protein_g: Mapped[float] = mapped_column(Float, nullable=False)
    target_fat_g: Mapped[float] = mapped_column(Float, nullable=False)
    target_water_ml: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)

    def to_domain(self) -> DailyGoal:
        return DailyGoal(
            id=self.id,
            user_id=self.user_id,
            target_kcal=self.target_kcal,
            target_carbs_g=self.target_carbs_g,
            target_protein_g=self.target_protein_g,
            target_fat_g=self.target_fat_g,
            target_water_ml=self.target_water_ml,
            effective_date=self.effective_date,
        )

    @staticmethod
    def from_domain(goal: DailyGoal) -> DailyGoalORM:
        return DailyGoalORM(
            id=goal.id,
            user_id=goal.user_id,
            target_kcal=goal.target_kcal,
            target_carbs_g=goal.target_carbs_g,
            target_protein_g=goal.target_protein_g,
            target_fat_g=goal.target_fat_g,
            target_water_ml=goal.target_water_ml,
            effective_date=goal.effective_date,
        )
