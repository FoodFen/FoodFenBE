"""Persistence port for food entries. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from src.domain.entities.food_entry import FoodEntry


class FoodEntryRepositoryProtocol(Protocol):
    async def create(self, entry: FoodEntry) -> FoodEntry: ...

    async def get_by_id(self, entry_id: UUID) -> FoodEntry | None: ...

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[FoodEntry]:
        """Inclusive range, filtered on ``logged_on``."""
        ...

    async def update(self, entry: FoodEntry) -> FoodEntry:
        """Full replace, including ``ingredients``. Raise
        ``FoodEntryNotFoundException`` if ``entry.id`` doesn't exist or is
        soft-deleted."""
        ...

    async def delete(self, entry_id: UUID) -> None:
        """Soft delete. Raise ``FoodEntryNotFoundException`` if it doesn't
        exist or is already deleted."""
        ...
