"""Use case: log a meal.

``fiber_g`` is always stored exactly as submitted — Premium only gates its
*display* client-side (mirrors the AI food-capture endpoints, which apply no
Premium check either). Dropping it server-side would permanently lose data
for a free user who later upgrades and re-pulls their history.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.food_entry import CreateFoodEntryInputDTO, FoodEntryOutputDTO
from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient


@dataclass
class CreateFoodEntryUseCase:
    food_entries: FoodEntryRepositoryProtocol

    async def execute(self, input_dto: CreateFoodEntryInputDTO) -> FoodEntryOutputDTO:
        entry = FoodEntry.create(
            user_id=input_dto.user_id,
            name=input_dto.name,
            input_method=input_dto.input_method,
            total_kcal=input_dto.total_kcal,
            carbs_g=input_dto.carbs_g,
            protein_g=input_dto.protein_g,
            fat_g=input_dto.fat_g,
            meal_type=input_dto.meal_type,
            client_id=input_dto.client_id,
            image_url=input_dto.image_url,
            fiber_g=input_dto.fiber_g,
            logged_at=input_dto.logged_at,
            logged_on=input_dto.logged_on,
        )
        entry.ingredients = [
            Ingredient.create(
                food_entry_id=entry.id,
                name=i.name,
                quantity_g=i.quantity_g,
                kcal=i.kcal,
                carbs_g=i.carbs_g,
                protein_g=i.protein_g,
                fat_g=i.fat_g,
                fiber_g=i.fiber_g,
            )
            for i in (input_dto.ingredients or [])
        ]
        entry = await self.food_entries.create(entry)
        return FoodEntryOutputDTO.from_entity(entry)
