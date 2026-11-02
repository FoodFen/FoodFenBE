"""Persistence port for the server-side food catalog."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.catalog_food import CatalogFood


class FoodCatalogRepositoryProtocol(Protocol):
    async def list_active(self) -> list[CatalogFood]:
        """Non-archived foods, ordered by slug."""
        ...

    async def get_by_slug(self, slug: str) -> CatalogFood | None:
        """Archived foods included; the caller reads ``archived``."""
        ...
