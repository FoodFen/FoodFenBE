"""CoinTransaction entity — an append-only ledger line for the in-app currency."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.enums import CoinReason
from src.domain.exceptions import InvalidAttributeException


@dataclass
class CoinTransaction:
    """One balance movement.

    ``amount`` is signed: positive credits (quest reward, streak bonus), negative
    debits (a purchase). Zero is rejected — a ledger line that moves nothing is a
    bug, not a record. The balance is the sum of these rows, never a stored field.
    """

    id: UUID
    user_id: int
    amount: int
    reason: CoinReason
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.amount == 0:
            raise InvalidAttributeException("amount must not be zero")

    @classmethod
    def create(cls, user_id: int, amount: int, reason: CoinReason) -> CoinTransaction:
        return cls(
            id=uuid4(),
            user_id=user_id,
            amount=amount,
            reason=reason,
            created_at=datetime.now(UTC),
        )
