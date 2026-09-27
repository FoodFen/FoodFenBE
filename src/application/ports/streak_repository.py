"""Persistence port for streaks. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.streak import Streak


class StreakRepositoryProtocol(Protocol):
    async def upsert(self, streak: Streak) -> Streak:
        """One row per user_id — replaces it if one already exists,
        creates it (preserving the given id) otherwise."""
        ...
