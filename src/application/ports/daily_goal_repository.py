"""Persistence port for daily goals. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.daily_goal import DailyGoal


class DailyGoalRepositoryProtocol(Protocol):
    async def list_by_user(self, user_id: int) -> list[DailyGoal]: ...
