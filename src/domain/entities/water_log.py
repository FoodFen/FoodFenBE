"""WaterLog entity — one drink."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.validation import require_positive


@dataclass
class WaterLog:
    id: UUID
    user_id: UUID
    amount_ml: int
    logged_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        require_positive(self.amount_ml, "amount_ml")

    @classmethod
    def create(cls, user_id: UUID, amount_ml: int) -> WaterLog:
        return cls(
            id=uuid4(),
            user_id=user_id,
            amount_ml=amount_ml,
            logged_at=datetime.now(UTC),
        )
