"""Use case: the mascot catalogue with what the user owns and has equipped."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.mascot import MascotOutputDTO, MascotsOutputDTO
from src.application.ports.coin_repository import CoinRepositoryProtocol
from src.application.ports.mascot_repository import MascotRepositoryProtocol

FREE_MASCOT_ID = "default"


@dataclass
class GetMascotsUseCase:
    coins: CoinRepositoryProtocol
    mascots: MascotRepositoryProtocol

    async def execute(self, user_id: int) -> MascotsOutputDTO:
        catalogue = await self.mascots.list_active()
        bought = await self.mascots.owned_ids(user_id)
        equipped = await self.mascots.get_equipped(user_id)
        return MascotsOutputDTO(
            balance=await self.coins.balance(user_id),
            # A mascot deactivated after being equipped reads as the free one (no write).
            equipped_id=equipped if any(m.id == equipped for m in catalogue) else FREE_MASCOT_ID,
            mascots=[
                MascotOutputDTO(m.id, m.name, m.coin_cost, owned=m.coin_cost == 0 or m.id in bought)
                for m in catalogue
            ],
        )
