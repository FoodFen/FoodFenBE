"""CoinBundle entity — a Premium-days pack that can be bought with coins."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.domain.validation import require_positive


@dataclass
class CoinBundle:
    id: UUID
    days: int
    coin_cost: int

    def __post_init__(self) -> None:
        require_positive(self.days, "days")
        require_positive(self.coin_cost, "coin_cost")
