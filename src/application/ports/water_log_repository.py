"""Persistence port for water logs. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from src.domain.entities.water_log import WaterLog


class WaterLogRepositoryProtocol(Protocol):
    async def create(self, log: WaterLog) -> WaterLog: ...

    async def get_by_id(self, log_id: UUID) -> WaterLog | None: ...

    async def update(self, log: WaterLog) -> WaterLog:
        """Full replace. Raise ``WaterLogNotFoundException`` if it doesn't
        exist or is soft-deleted."""
        ...

    async def delete(self, log_id: UUID) -> None:
        """Soft delete. Raise ``WaterLogNotFoundException`` if it doesn't
        exist or is already deleted."""
        ...

    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[WaterLog]:
        """Inclusive range, filtered on ``logged_on``."""
        ...
