"""HTTP wire models for quests and coin redemption."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from src.adapters.schemas.base import CamelModel
from src.adapters.schemas.subscription_schemas import SubscriptionResponse
from src.application.dtos.coin import QuestOutputDTO, QuestsOutputDTO, RedeemOutputDTO
from src.domain.enums import QuestCadence, QuestType


class QuestResponse(CamelModel):
    id: UUID
    quest_type: QuestType
    cadence: QuestCadence
    quest_date: date
    progress: int
    target: int
    reward_coins: int
    completed: bool

    @classmethod
    def from_dto(cls, dto: QuestOutputDTO) -> QuestResponse:
        return cls(**vars(dto))


class QuestsResponse(CamelModel):
    balance: int
    quests: list[QuestResponse]

    @classmethod
    def from_dto(cls, dto: QuestsOutputDTO) -> QuestsResponse:
        return cls(balance=dto.balance, quests=[QuestResponse.from_dto(q) for q in dto.quests])


class RedeemRequest(CamelModel):
    days: int


class RedeemResponse(CamelModel):
    balance: int
    subscription: SubscriptionResponse

    @classmethod
    def from_dto(cls, dto: RedeemOutputDTO) -> RedeemResponse:
        return cls(balance=dto.balance, subscription=SubscriptionResponse.from_dto(dto.subscription))
