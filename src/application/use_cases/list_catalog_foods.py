"""Use case: the public food catalog for Mobile sync (everything, or what changed since a cursor)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from src.application.dtos.food_admin import AdminFoodDTO
from src.application.dtos.food_catalog import CatalogSyncDTO
from src.application.ports.food_catalog_repository import FoodCatalogRepositoryProtocol


@dataclass
class ListCatalogFoodsUseCase:
    foods: FoodCatalogRepositoryProtocol

    async def execute(self, updated_since: datetime | None = None) -> CatalogSyncDTO:
        # The clock is read BEFORE the query: a food written while it runs is fetched again next time, never missed.
        server_time = datetime.now(UTC)
        foods = await self.foods.list_changed(updated_since and updated_since.astimezone(UTC))
        return CatalogSyncDTO([AdminFoodDTO.from_entity(f) for f in foods], server_time)
