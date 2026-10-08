"""Use case: partial dish edit. Any edit sends the dish back to pending (hidden until re-approved)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from src.application.dtos.restaurant import DishOutputDTO, UpdateDishInputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_dish


@dataclass
class UpdateDishUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, data: UpdateDishInputDTO) -> DishOutputDTO:
        current = await owned_dish(self.restaurants, data.user_id, data.dish_id)
        dish = replace(current, **data.updates)
        dish.mark_edited(datetime.now(UTC))
        await self.restaurants.update_dish(dish)
        return DishOutputDTO.from_entity(dish)
