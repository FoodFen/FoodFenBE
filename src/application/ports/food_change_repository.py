"""Persistence port for the catalog audit log (append-only)."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.entities.food_change import FoodChange


class FoodChangeRepositoryProtocol(Protocol):
    async def add(self, change: FoodChange) -> None: ...

    async def list_for_food(self, food_id: UUID) -> list[tuple[FoodChange, str | None]]:
        """Newest first (``id`` breaks ties), each with the admin's email (``None`` if the admin is gone)."""
        ...
