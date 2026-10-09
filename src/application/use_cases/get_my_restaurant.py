"""Use case: the caller's restaurant, with its moderation status."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.restaurant import RestaurantOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_restaurant


@dataclass
class GetMyRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, user_id: int) -> RestaurantOutputDTO:
        return RestaurantOutputDTO.from_entity(await owned_restaurant(self.restaurants, user_id))
