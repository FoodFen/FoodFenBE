"""ORM model for the quest catalog (what gets issued to users each day/week)."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.quest_definition import QuestDefinition
from src.domain.enums import QuestCadence, QuestType
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class QuestDefinitionORM(UUIDPrimaryKey, Base):
    __tablename__ = "quest_definitions"
    # One definition per quest type: a user gets each type at most once a day anyway
    # (uq_quests_user_type_date), so a second row would never be issued.
    __table_args__ = (UniqueConstraint("quest_type", name="uq_quest_definitions_quest_type"),)

    quest_type: Mapped[QuestType] = mapped_column(
        enum_column(QuestType, "quest_type"), nullable=False
    )
    target: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, nullable=False)
    cadence: Mapped[QuestCadence] = mapped_column(enum_column(QuestCadence, "cadence"), nullable=False)
    completion_ratio: Mapped[float] = mapped_column(
        Float, nullable=False, server_default=text("1")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    title_vi: Mapped[str] = mapped_column(String(80), nullable=False)
    title_en: Mapped[str] = mapped_column(String(80), nullable=False)
    description_vi: Mapped[str] = mapped_column(String(200), nullable=False)
    description_en: Mapped[str] = mapped_column(String(200), nullable=False)

    def to_domain(self) -> QuestDefinition:
        return QuestDefinition(
            id=self.id,
            quest_type=self.quest_type,
            target=self.target,
            reward_coins=self.reward_coins,
            cadence=self.cadence,
            completion_ratio=self.completion_ratio,
            active=self.active,
            title_vi=self.title_vi,
            title_en=self.title_en,
            description_vi=self.description_vi,
            description_en=self.description_en,
        )
