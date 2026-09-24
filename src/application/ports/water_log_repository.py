"""Persistence port for water logs. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from src.domain.entities.water_log import WaterLog


class WaterLogRepositoryProtocol(Protocol):
    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WaterLog]:
        """Inclusive range, filtered on ``logged_on``."""
        ...
