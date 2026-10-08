"""Use case: every dish of the caller's restaurant, any status, with rejection reasons."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.restaurant import DishOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_restaurant


@dataclass
class ListMyDishesUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, user_id: int) -> list[DishOutputDTO]:
        restaurant = await owned_restaurant(self.restaurants, user_id)
        return [DishOutputDTO.from_entity(d) for d in await self.restaurants.list_dishes(restaurant.id)]
