"""Food miss — a food name the AI could not match to the catalog, counted per folded name."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.enums import FoodMissStatus


@dataclass
class FoodMiss:
    id: UUID
    key: str  # folded name, unique
    name: str  # display form of the first sighting
    language: str
    count: int
    first_seen_at: datetime
    last_seen_at: datetime
    status: FoodMissStatus
    resolved_food_id: UUID | None

    def ignore(self) -> None:
        self.status, self.resolved_food_id = FoodMissStatus.IGNORED, None

    def reopen(self) -> None:
        self.status, self.resolved_food_id = FoodMissStatus.OPEN, None

    def resolve(self, food_id: UUID) -> None:
        self.status, self.resolved_food_id = FoodMissStatus.RESOLVED, food_id
