"""Use case: full-replace an existing food entry (incl. its ingredients).

Ownership check mirrors ``GetFoodEntryUseCase``: "doesn't exist" and
"belongs to someone else" both raise the same not-found exception so
existence isn't leaked.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.food_entry import FoodEntryOutputDTO, UpdateFoodEntryInputDTO
from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient
from src.domain.exceptions import FoodEntryNotFoundException


@dataclass
class UpdateFoodEntryUseCase:
    food_entries: FoodEntryRepositoryProtocol

    async def execute(
        self, user_id: int, entry_id: UUID, input_dto: UpdateFoodEntryInputDTO
    ) -> FoodEntryOutputDTO:
        existing = await self.food_entries.get_by_id(entry_id)
        if existing is None or existing.user_id != user_id:
            raise FoodEntryNotFoundException(f"no food entry {entry_id}")

        entry = FoodEntry(
            id=entry_id,
            user_id=user_id,
            name=input_dto.name,
            input_method=input_dto.input_method,
            total_kcal=input_dto.total_kcal,
            carbs_g=input_dto.carbs_g,
            protein_g=input_dto.protein_g,
            fat_g=input_dto.fat_g,
            meal_type=input_dto.meal_type,
            client_id=existing.client_id,
            image_url=input_dto.image_url,
            fiber_g=input_dto.fiber_g,
            ai_feedback=existing.ai_feedback,
            logged_at=existing.logged_at,
            logged_on=input_dto.logged_on or existing.logged_on,
            ingredients=[
                Ingredient.create(
                    food_entry_id=entry_id,
                    name=i.name,
                    quantity_g=i.quantity_g,
                    kcal=i.kcal,
                    carbs_g=i.carbs_g,
                    protein_g=i.protein_g,
                    fat_g=i.fat_g,
                    fiber_g=i.fiber_g,
                )
                for i in (input_dto.ingredients or [])
            ],
        )
        updated = await self.food_entries.update(entry)
        return FoodEntryOutputDTO.from_entity(updated)
