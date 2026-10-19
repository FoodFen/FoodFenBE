"""Persistence port for the mascot catalogue, ownership and the equipped choice."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.mascot import Mascot


class MascotRepositoryProtocol(Protocol):
    async def list_active(self) -> list[Mascot]:
        """Active mascots, cheapest first (then by id)."""
        ...

    async def get_active(self, mascot_id: str) -> Mascot | None: ...

    async def owned_ids(self, user_id: int) -> set[str]:
        """Ids the user bought. Free mascots have no row; they are owned by definition."""
        ...

    async def add_owned(self, user_id: int, mascot_id: str) -> None: ...

    async def get_equipped(self, user_id: int) -> str: ...

    async def set_equipped(self, user_id: int, mascot_id: str) -> None: ...
