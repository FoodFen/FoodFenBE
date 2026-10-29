"""Use case: approve, reject, or take down a restaurant. Idempotent.

Returns a notice for the owner only when the status actually changed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from src.application.dtos.restaurant import (
    RestaurantOutputDTO,
    RestaurantReviewResultDTO,
    ReviewNoticeDTO,
)
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.enums import ModerationStatus, ReviewDecision
from src.domain.exceptions import RestaurantNotFoundException, StaleReviewException


@dataclass
class ReviewRestaurantUseCase:
    restaurants: RestaurantRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(
        self,
        restaurant_id: UUID,
        decision: ReviewDecision,
        reason: str | None,
        expected_updated_at: datetime | None,
    ) -> RestaurantReviewResultDTO:
        restaurant = await self.restaurants.get_by_id(restaurant_id)
        if restaurant is None:
            raise RestaurantNotFoundException(f"restaurant {restaurant_id} not found")
        if expected_updated_at is not None and expected_updated_at != restaurant.updated_at:
            raise StaleReviewException("changed since you loaded it; reload and review again")
        before = restaurant.status
        restaurant.review(decision, reason, datetime.now(UTC))
        await self.restaurants.update(restaurant)
        notice = None
        owner = await self.users.get_by_id(restaurant.user_id) if restaurant.status != before else None
        if owner is not None:
            notice = ReviewNoticeDTO(
                email=owner.email,
                name=owner.name,
                restaurant_name=restaurant.name,
                approved=restaurant.status == ModerationStatus.APPROVED,
                reason=restaurant.rejection_reason,
            )
        return RestaurantReviewResultDTO(RestaurantOutputDTO.from_entity(restaurant), notice)
