"""Persistence port for the server-side food catalog."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.domain.entities.catalog_food import CatalogFood


class FoodCatalogRepositoryProtocol(Protocol):
    async def list_active(self) -> list[CatalogFood]:
        """Non-archived foods, ordered by slug."""
        ...

    async def get_by_slug(self, slug: str) -> CatalogFood | None:
        """Archived foods included; the caller reads ``archived``."""
        ...

    async def list_all(self) -> list[CatalogFood]:
        """Every food, archived included, in no particular order."""
        ...

    async def list_changed(self, since: datetime | None) -> list[CatalogFood]:
        """Archived included, ordered by slug: foods with ``updated_at >= since``, or every food when ``since`` is None."""
        ...

    async def add(self, food: CatalogFood) -> None: ...

    async def update(self, food: CatalogFood) -> None:
        """Write every mutable field of ``food`` (looked up by ``id``)."""
        ...
