"""Persistence port for restaurants and their dishes (one aggregate)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.application.dtos.admin import AdminRestaurantRowDTO
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.enums import ModerationStatus


class RestaurantRepositoryProtocol(Protocol):
    async def add(self, restaurant: Restaurant) -> None:
        """Raise ``RestaurantAlreadyExistsException`` if the owner already has one."""
        ...

    async def get_by_id(self, restaurant_id: UUID) -> Restaurant | None: ...

    async def get_by_owner(self, user_id: int) -> Restaurant | None: ...

    async def update(self, restaurant: Restaurant) -> None: ...

    async def list_for_admin(
        self, needs_review: bool, status: ModerationStatus | None
    ) -> list[AdminRestaurantRowDTO]:
        """Oldest ``updated_at`` first. ``needs_review``: pending restaurants, or approved ones
        with at least one pending dish."""
        ...

    async def add_dish(self, dish: Dish) -> None: ...

    async def get_dish(self, dish_id: UUID) -> Dish | None: ...

    async def update_dish(self, dish: Dish) -> None: ...

    async def delete_dish(self, dish_id: UUID) -> None: ...

    async def list_dishes(self, restaurant_id: UUID) -> list[Dish]:
        """Every status, oldest first."""
        ...
