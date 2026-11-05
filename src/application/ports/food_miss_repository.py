"""Persistence port for the AI's unmatched food names."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from src.domain.entities.food_miss import FoodMiss
from src.domain.enums import FoodMissStatus


class FoodMissRepositoryProtocol(Protocol):
    async def record(self, misses: Sequence[tuple[str, str]], language: str, at: datetime) -> None:
        """Upsert ``(key, display name)`` pairs (distinct keys) in one statement, isolated from the caller's
        transaction. A known key gets ``count + 1`` and ``last_seen_at``; its name, language and status are kept."""
        ...

    async def list(self, status: FoodMissStatus, offset: int, limit: int) -> tuple[list[FoodMiss], int]:
        """One page plus the total of that status, ordered ``count`` desc, ``last_seen_at`` desc, ``id``."""
        ...

    async def get(self, miss_id: UUID) -> FoodMiss | None: ...

    async def update(self, miss: FoodMiss) -> None:
        """Write ``status`` and ``resolved_food_id``."""
        ...

    async def resolve_open(self, keys: Collection[str], food_id: UUID) -> None:
        """Mark every ``open`` miss whose key is in ``keys`` as resolved by ``food_id``."""
        ...
