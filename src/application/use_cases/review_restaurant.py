"""Use case: approve, reject, or take down a restaurant. Idempotent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.dtos.restaurant import RestaurantOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.enums import ReviewDecision
from src.domain.exceptions import RestaurantNotFoundException


@dataclass
class ReviewRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(
        self, restaurant_id: UUID, decision: ReviewDecision, reason: str | None
    ) -> RestaurantOutputDTO:
        restaurant = await self.restaurants.get_by_id(restaurant_id)
        if restaurant is None:
            raise RestaurantNotFoundException(f"restaurant {restaurant_id} not found")
        restaurant.review(decision, reason, datetime.now(UTC))
        await self.restaurants.update(restaurant)
        return RestaurantOutputDTO.from_entity(restaurant)
