"""Food change — one append-only audit row: who changed a catalog food, and its before / after snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from src.domain.enums import FoodChangeAction


@dataclass(frozen=True)
class FoodChange:
    id: UUID
    food_id: UUID
    admin_id: int | None  # None once the admin's account is gone
    action: FoodChangeAction
    before: dict | None  # None only for ``create``
    after: dict
    created_at: datetime

    @classmethod
    def create(
        cls, food_id: UUID, admin_id: int, action: FoodChangeAction, before: dict | None, after: dict, now: datetime
    ) -> FoodChange:
        return cls(uuid4(), food_id, admin_id, action, before, after, now)
