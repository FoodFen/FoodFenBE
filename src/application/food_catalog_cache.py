"""Process-wide cache of the active food catalog, so a request doesn't reload ~670 rows and the
prompt's catalog block stays byte-identical between requests."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from src.application.ports.food_catalog_repository import FoodCatalogRepositoryProtocol
from src.domain.entities.catalog_food import CatalogFood


@dataclass
class FoodCatalogCache:
    ttl_seconds: float = 600  # fallback; admin catalog edits call invalidate()
    _foods: dict[str, CatalogFood] = field(default_factory=dict, init=False)
    _loaded_at: float = field(default=0.0, init=False)

    async def get(self, repo: FoodCatalogRepositoryProtocol) -> dict[str, CatalogFood]:
        """slug -> food in repo (slug) order. No lock: two concurrent reloads are harmless."""
        if not self._foods or time.monotonic() - self._loaded_at >= self.ttl_seconds:
            self._foods = {f.slug: f for f in await repo.list_active()}
            self._loaded_at = time.monotonic()
        return self._foods

    def invalidate(self) -> None:
        self._foods = {}
