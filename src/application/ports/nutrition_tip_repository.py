"""Persistence port for nutrition tips."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.entities.nutrition_tip import NutritionTip


class NutritionTipRepositoryProtocol(Protocol):
    async def list(self, active_only: bool) -> list[NutritionTip]:
        """Newest first."""
        ...

    async def get(self, tip_id: UUID) -> NutritionTip | None: ...

    async def add(self, tip: NutritionTip) -> None: ...

    async def update(self, tip: NutritionTip) -> None: ...

    async def delete(self, tip_id: UUID) -> None: ...
