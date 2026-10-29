"""HTTP wire models for quests and coin redemption."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, Field

from src.adapters.schemas.base import CamelModel
from src.adapters.schemas.subscription_schemas import SubscriptionResponse
from src.application.dtos.coin import (
    CoinBundleOutputDTO,
    CoinTransactionsPageDTO,
    QuestOutputDTO,
    QuestsOutputDTO,
    RedeemOutputDTO,
)
from src.application.chat_cursor import decode_cursor
from src.domain.enums import CoinReason, QuestCadence, QuestType, QuestUnit
from src.domain.exceptions import InvalidAttributeException


def _check_cursor(value: str) -> str:
    # Pydantic only turns ValueError into a validation error; the mobile contract wants 422 here.
    try:
        decode_cursor(value)
    except InvalidAttributeException as exc:
        raise ValueError(str(exc)) from exc
    return value


CursorQuery = Annotated[str, AfterValidator(_check_cursor)]


class QuestResponse(CamelModel):
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
    client_id: str | None = Field(default=None, min_length=1, max_length=64)


class RedeemResponse(CamelModel):
    balance: int
    subscription: SubscriptionResponse

    @classmethod
    def from_dto(cls, dto: RedeemOutputDTO) -> RedeemResponse:
        return cls(balance=dto.balance, subscription=SubscriptionResponse.from_dto(dto.subscription))


class CoinBundleResponse(CamelModel):
    id: UUID
    days: int
    coin_cost: int


class CoinBundlesResponse(CamelModel):
    bundles: list[CoinBundleResponse]

    @classmethod
    def from_dtos(cls, dtos: list[CoinBundleOutputDTO]) -> CoinBundlesResponse:
        return cls(bundles=[CoinBundleResponse(**vars(d)) for d in dtos])


class CoinTransactionResponse(CamelModel):
    id: UUID
    amount: int
    reason: CoinReason
    created_at: datetime


class CoinTransactionsResponse(CamelModel):
    transactions: list[CoinTransactionResponse]
    next_cursor: str | None

    @classmethod
    def from_dto(cls, dto: CoinTransactionsPageDTO) -> CoinTransactionsResponse:
        return cls(
            transactions=[CoinTransactionResponse(**vars(t)) for t in dto.transactions],
            next_cursor=dto.next_cursor,
        )
