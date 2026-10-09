"""Use case: a restaurant's public profile with its approved dishes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.restaurant import PublicDishDTO, PublicRestaurantDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.enums import ModerationStatus
from src.domain.exceptions import RestaurantNotFoundException


@dataclass
class GetPublicRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, restaurant_id: UUID) -> PublicRestaurantDTO:
        r = await self.restaurants.get_by_id(restaurant_id)
        if r is None or r.status != ModerationStatus.APPROVED:
            raise RestaurantNotFoundException(f"restaurant {restaurant_id} not found")
        dishes = await self.restaurants.list_dishes(restaurant_id)
        return PublicRestaurantDTO(
            id=r.id, name=r.name, description=r.description, address=r.address, phone=r.phone,
            opening_hours=r.opening_hours, latitude=r.latitude, longitude=r.longitude,
            image_url=r.image_url,
            dishes=[PublicDishDTO.from_entity(d) for d in dishes if d.status == ModerationStatus.APPROVED],
        )
