"""Use case: the mascot catalogue with what the user owns and has equipped."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.mascot import MascotOutputDTO, MascotsOutputDTO
from src.application.ports.coin_repository import CoinRepositoryProtocol
from src.application.ports.mascot_repository import MascotRepositoryProtocol
from src.domain.entities.mascot import FREE_MASCOT_ID


@dataclass
class GetMascotsUseCase:
    coins: CoinRepositoryProtocol
    mascots: MascotRepositoryProtocol

    async def execute(self, user_id: int | None) -> MascotsOutputDTO:
        """``None`` is a signed-out guest: what a brand-new account sees (nothing bought, free one equipped)."""
        catalogue = await self.mascots.list_active()
        bought = await self.mascots.owned_ids(user_id) if user_id is not None else set()
        equipped = await self.mascots.get_equipped(user_id) if user_id is not None else FREE_MASCOT_ID
        return MascotsOutputDTO(
            balance=await self.coins.balance(user_id) if user_id is not None else 0,
            # A mascot deactivated after being equipped reads as the free one (no write).
            equipped_id=equipped if any(m.id == equipped for m in catalogue) else FREE_MASCOT_ID,
            mascots=[
                MascotOutputDTO(
                    m.id, m.name, m.coin_cost, m.coin_cost == 0 or m.id in bought, m.images, m.body_color
                )
                for m in catalogue
            ],
        )
