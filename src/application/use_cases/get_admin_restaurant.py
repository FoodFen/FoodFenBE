"""Use case: one restaurant with its full menu and nutrition, for review."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.admin import AdminRestaurantDetailDTO
from src.application.dtos.restaurant import DishOutputDTO, RestaurantOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.exceptions import RestaurantNotFoundException


@dataclass
class GetAdminRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, restaurant_id: UUID) -> AdminRestaurantDetailDTO:
        restaurant = await self.restaurants.get_by_id(restaurant_id)
        if restaurant is None:
            raise RestaurantNotFoundException(f"restaurant {restaurant_id} not found")
        dishes = await self.restaurants.list_dishes(restaurant_id)
        return AdminRestaurantDetailDTO(
            restaurant=RestaurantOutputDTO.from_entity(restaurant),
            dishes=[DishOutputDTO.from_entity(d) for d in dishes],
        )
