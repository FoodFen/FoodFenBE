"""Use case: list food entries logged in an inclusive date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.application.dtos.food_entry import FoodEntryOutputDTO
from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol


@dataclass
class ListFoodEntriesUseCase:
    food_entries: FoodEntryRepositoryProtocol

    async def execute(self, user_id: int, from_date: date, to_date: date) -> list[FoodEntryOutputDTO]:
        entries = await self.food_entries.list_by_date_range(user_id, from_date, to_date)
        return [FoodEntryOutputDTO.from_entity(e) for e in entries]
