"""Mascot entity — a collectible companion; free when ``coin_cost`` is 0, otherwise bought with coins."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.validation import require_non_negative


@dataclass
class Mascot:
    id: str  # slug, e.g. "sprout" — the app ships artwork keyed by it
    name: str
    coin_cost: int

    def __post_init__(self) -> None:
        require_non_negative(self.coin_cost, "coin_cost")
