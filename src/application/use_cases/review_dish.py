"""Use case: approve or reject one dish. Idempotent.

Returns a notice for the owner only when the dish became rejected: approvals stay silent because
the web admin approves a whole menu with one request per dish."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.dtos.restaurant import DishOutputDTO, DishReviewResultDTO, ReviewNoticeDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.enums import ModerationStatus, ReviewDecision
from src.domain.exceptions import DishNotFoundException, StaleReviewException


@dataclass
class ReviewDishUseCase:
    restaurants: RestaurantRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(
        self,
        dish_id: UUID,
        decision: ReviewDecision,
        reason: str | None,
        expected_updated_at: datetime | None,
    ) -> DishReviewResultDTO:
        dish = await self.restaurants.get_dish(dish_id)
        if dish is None:
            raise DishNotFoundException(f"dish {dish_id} not found")
        if expected_updated_at is not None and expected_updated_at != dish.updated_at:
            raise StaleReviewException("changed since you loaded it; reload and review again")
        before = dish.status
        dish.review(decision, reason, datetime.now(UTC))
        await self.restaurants.update_dish(dish)
        notice = None
        if dish.status == ModerationStatus.REJECTED and before != dish.status:
            restaurant = await self.restaurants.get_by_id(dish.restaurant_id)
            owner = await self.users.get_by_id(restaurant.user_id) if restaurant else None
            if restaurant is not None and owner is not None:
                notice = ReviewNoticeDTO(
                    email=owner.email,
                    name=owner.name,
                    restaurant_name=restaurant.name,
                    approved=False,
                    reason=dish.rejection_reason,
                    dish_name=dish.name,
                )
        return DishReviewResultDTO(DishOutputDTO.from_entity(dish), notice)
