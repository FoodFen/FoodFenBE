"""Coin & quest DTOs — frozen dataclasses, never Pydantic models or ORM rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from src.application.dtos.subscription import SubscriptionOutputDTO
from src.domain.entities.quest import Quest
from src.domain.enums import QuestCadence, QuestType, QuestUnit


@dataclass(frozen=True)
class QuestOutputDTO:
    id: UUID
    quest_type: QuestType
    cadence: QuestCadence
    quest_date: date
    progress: int
    target: int
    reward_coins: int
    completed: bool
    completion_ratio: float
    unit: QuestUnit
    title: str
    description: str

    @classmethod
    def from_entity(cls, quest: Quest, title: str, description: str) -> QuestOutputDTO:
        return cls(
            id=quest.id,
            quest_type=quest.quest_type,
            cadence=quest.cadence,
            quest_date=quest.quest_date,
            progress=quest.progress,
            target=quest.target,
            reward_coins=quest.reward_coins,
            completed=quest.completed,
            completion_ratio=quest.completion_ratio,
            unit=quest.unit,
            title=title,
            description=description,
        )


@dataclass(frozen=True)
class QuestsOutputDTO:
    balance: int
    quests: list[QuestOutputDTO]


@dataclass(frozen=True)
class RedeemOutputDTO:
    balance: int
    subscription: SubscriptionOutputDTO


@dataclass(frozen=True)
class CoinBundleOutputDTO:
    id: UUID
    days: int
    coin_cost: int
