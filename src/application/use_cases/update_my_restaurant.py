"""Use case: partial profile edit. Approved stays live; rejected is resubmitted (see entity)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from src.application.dtos.restaurant import RestaurantOutputDTO, UpdateRestaurantInputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.use_cases.restaurant_support import owned_restaurant


@dataclass
class UpdateMyRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(self, data: UpdateRestaurantInputDTO) -> RestaurantOutputDTO:
        current = await owned_restaurant(self.restaurants, data.user_id)
        if not data.updates:  # empty PATCH is a no-op: must not resubmit a rejected restaurant
            return RestaurantOutputDTO.from_entity(current)
        restaurant = replace(current, **data.updates)  # re-runs __post_init__: invariants re-checked
        restaurant.mark_edited(datetime.now(UTC))
        await self.restaurants.update(restaurant)
        return RestaurantOutputDTO.from_entity(restaurant)
