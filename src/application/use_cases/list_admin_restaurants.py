"""Use case: the admin's restaurant list / review queue."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.admin import AdminRestaurantListDTO
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.enums import ModerationStatus


@dataclass
class ListAdminRestaurantsUseCase:
    restaurants: RestaurantRepositoryProtocol

    async def execute(
        self,
        needs_review: bool,
        status: ModerationStatus | None,
        q: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> AdminRestaurantListDTO:
        rows, total = await self.restaurants.list_for_admin(needs_review, status, q, offset, limit)
        page_end = offset + limit
        return AdminRestaurantListDTO(
            restaurants=rows, total=total, next_cursor=str(page_end) if page_end < total else None
        )
