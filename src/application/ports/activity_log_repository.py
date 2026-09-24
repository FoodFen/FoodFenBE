"""Persistence port for activity logs. Structural typing via Protocol."""

from __future__ import annotations

from datetime import date
from typing import Protocol

from src.domain.entities.activity_log import ActivityLog


class ActivityLogRepositoryProtocol(Protocol):
    async def list_by_date_range(
        self, user_id: int, from_date: date, to_date: date
    ) -> list[ActivityLog]:
        """Inclusive range, filtered on ``logged_on``."""
        ...
