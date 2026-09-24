"""WaterLog entity — one drink."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.validation import require_non_empty, require_positive


@dataclass
class WaterLog:
    id: UUID
    user_id: int
    amount_ml: int
    client_id: str
    logged_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    logged_on: date = field(default_factory=lambda: datetime.now(UTC).date())

    def __post_init__(self) -> None:
        require_positive(self.amount_ml, "amount_ml")
        self.client_id = require_non_empty(self.client_id, "client_id")

    @classmethod
    def create(
        cls, user_id: int, amount_ml: int, *, client_id: str, logged_on: date | None = None
    ) -> WaterLog:
        logged_at = datetime.now(UTC)
        return cls(
            id=uuid4(),
            user_id=user_id,
            amount_ml=amount_ml,
            client_id=client_id,
            logged_at=logged_at,
            logged_on=logged_on or logged_at.date(),
        )
