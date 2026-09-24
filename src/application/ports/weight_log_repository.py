"""Persistence port for weight logs. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from src.domain.entities.weight_log import WeightLog


class WeightLogRepositoryProtocol(Protocol):
    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WeightLog]:
        """Inclusive range, filtered on ``recorded_at``."""
        ...
