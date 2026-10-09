"""Use case: the admin's restaurant list / review queue."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.admin import AdminRestaurantRowDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.enums import ModerationStatus


@dataclass
class ListAdminRestaurantsUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(
        self, needs_review: bool, status: ModerationStatus | None
    ) -> list[AdminRestaurantRowDTO]:
        # ponytail: unpaginated; add a cursor once the queue routinely holds hundreds of rows.
        return await self.restaurants.list_for_admin(needs_review, status)
