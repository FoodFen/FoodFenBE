"""Use case: add a dish (pending) to the caller's restaurant."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.application.dtos.restaurant import CreateDishInputDTO, DishOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_restaurant
from src.domain.entities.dish import Dish


@dataclass
class CreateDishUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, data: CreateDishInputDTO) -> DishOutputDTO:
        restaurant = await owned_restaurant(self.restaurants, data.user_id)
        fields = asdict(data)
        del fields["user_id"]
        dish = Dish.create(restaurant_id=restaurant.id, **fields)
        await self.restaurants.add_dish(dish)
        return DishOutputDTO.from_entity(dish)
