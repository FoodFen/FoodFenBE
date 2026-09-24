"""Use case: read a single food entry, owned by the requesting user."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.food_entry import FoodEntryOutputDTO
from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol
from src.domain.exceptions import FoodEntryNotFoundException


@dataclass
class GetFoodEntryUseCase:
    food_entries: FoodEntryRepositoryProtocol

    async def execute(self, user_id: int, entry_id: UUID) -> FoodEntryOutputDTO:
        entry = await self.food_entries.get_by_id(entry_id)
        if entry is None or entry.user_id != user_id:
            raise FoodEntryNotFoundException(f"no food entry {entry_id}")
        return FoodEntryOutputDTO.from_entity(entry)
