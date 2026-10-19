"""Use case: choose which owned mascot the app shows."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.mascot_repository import MascotRepositoryProtocol
from src.domain.exceptions import MascotNotFoundException, MascotNotOwnedException


@dataclass
class EquipMascotUseCase:
    mascots: MascotRepositoryProtocol

    async def execute(self, user_id: int, mascot_id: str) -> str:
        mascot = await self.mascots.get_active(mascot_id)
        if mascot is None:
            raise MascotNotFoundException(f"no mascot {mascot_id!r}")
        if mascot.coin_cost > 0 and mascot_id not in await self.mascots.owned_ids(user_id):
            raise MascotNotOwnedException(f"mascot {mascot_id!r} is not yours yet")
        await self.mascots.set_equipped(user_id, mascot_id)
        return mascot_id
