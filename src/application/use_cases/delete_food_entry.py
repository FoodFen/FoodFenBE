"""Use case: soft-delete a food entry."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol
from src.domain.exceptions import FoodEntryNotFoundException


@dataclass
class DeleteFoodEntryUseCase:
    food_entries: FoodEntryRepositoryProtocol

    async def execute(self, user_id: int, entry_id: UUID) -> None:
        existing = await self.food_entries.get_by_id(entry_id)
        if existing is None or existing.user_id != user_id:
            raise FoodEntryNotFoundException(f"no food entry {entry_id}")
        await self.food_entries.delete(entry_id)
