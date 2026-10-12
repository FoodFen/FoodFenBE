"""Persistence port for the sponsored section's daily impression counters."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Protocol
from uuid import UUID


class AdImpressionRepositoryProtocol(Protocol):
    async def increment(self, restaurant_ids: Sequence[UUID], day: date) -> None:
        """Add one impression on ``day`` to each restaurant (atomic upsert)."""
        ...

    async def counts(self, restaurant_id: UUID, first: date, last: date) -> dict[date, int]:
        """Impressions per day for days ``first..last`` inclusive; days with none are absent."""
        ...
