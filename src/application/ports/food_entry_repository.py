"""Persistence port for food entries. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.entities.food_entry import FoodEntry


class FoodEntryRepositoryProtocol(Protocol):
    async def create(self, entry: FoodEntry) -> FoodEntry: ...

    async def get_by_id(self, entry_id: UUID) -> FoodEntry | None: ...
