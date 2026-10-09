"""Use case: a user registers their (single) restaurant. It starts pending."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from src.application.dtos.restaurant import CreateRestaurantInputDTO, RestaurantOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.entities.restaurant import Restaurant
from src.domain.exceptions import RestaurantAlreadyExistsException


@dataclass
class CreateRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, data: CreateRestaurantInputDTO) -> RestaurantOutputDTO:
        if await self.restaurants.get_by_owner(data.user_id) is not None:
            raise RestaurantAlreadyExistsException("you already have a restaurant")
        restaurant = Restaurant.create(**asdict(data))
        await self.restaurants.add(restaurant)  # also raises on a concurrent duplicate
        return RestaurantOutputDTO.from_entity(restaurant)
