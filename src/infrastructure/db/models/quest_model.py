"""ORM model for quests."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, Float, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.quest import Quest
from src.domain.enums import QuestCadence, QuestType
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class QuestORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "quests"
    # A user gets each quest type at most once a day, so a retried assignment
    # job cannot hand out the same reward twice.
    __table_args__ = (
        UniqueConstraint("user_id", "quest_type", "quest_date", name="uq_quests_user_type_date"),
    )

    quest_type: Mapped[QuestType] = mapped_column(
        enum_column(QuestType, "quest_type"), nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False)
    completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    quest_date: Mapped[date] = mapped_column(Date, nullable=False)
    cadence: Mapped[QuestCadence] = mapped_column(
        enum_column(QuestCadence, "cadence"),
        nullable=False,
        server_default=QuestCadence.DAILY.value,
    )
    completion_ratio: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("1")
    )

    def to_domain(self) -> Quest:
        return Quest(
            id=self.id,
            user_id=self.user_id,
            quest_type=self.quest_type,
            target=self.target,
            reward_coins=self.reward_coins,
            progress=self.progress,
            completed=self.completed,
            quest_date=self.quest_date,
            cadence=self.cadence,
            completion_ratio=self.completion_ratio,
        )

    @staticmethod
    def from_domain(quest: Quest) -> QuestORM:
        return QuestORM(
            id=quest.id,
            user_id=quest.user_id,
            quest_type=quest.quest_type,
            target=quest.target,
            reward_coins=quest.reward_coins,
            progress=quest.progress,
            completed=quest.completed,
            quest_date=quest.quest_date,
            cadence=quest.cadence,
            completion_ratio=quest.completion_ratio,
        )
