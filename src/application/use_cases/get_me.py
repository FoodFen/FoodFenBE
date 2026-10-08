"""Use case: the signed-in user plus the id of the restaurant they own, if any."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.user import MeOutputDTO, UserOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.entities.user import User


@dataclass
class GetMeUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, user: User) -> MeOutputDTO:
        restaurant = await self.restaurants.get_by_owner(user.id)
        return MeOutputDTO(
            user=UserOutputDTO.from_entity(user),
            restaurant_id=restaurant.id if restaurant else None,
        )
