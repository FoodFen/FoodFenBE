"""Use case: approve or reject one dish. Idempotent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.dtos.restaurant import DishOutputDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.enums import ReviewDecision
from src.domain.exceptions import DishNotFoundException


@dataclass
class ReviewDishUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(
        self, dish_id: UUID, decision: ReviewDecision, reason: str | None
    ) -> DishOutputDTO:
        dish = await self.restaurants.get_dish(dish_id)
        if dish is None:
            raise DishNotFoundException(f"dish {dish_id} not found")
        dish.review(decision, reason, datetime.now(UTC))
        await self.restaurants.update_dish(dish)
        return DishOutputDTO.from_entity(dish)
