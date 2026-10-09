"""Use case: delete one of the caller's dishes outright (nothing references a dish yet)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_dish


@dataclass
class DeleteDishUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, user_id: int, dish_id: UUID) -> None:
        dish = await owned_dish(self.restaurants, user_id, dish_id)
        await self.restaurants.delete_dish(dish.id)
