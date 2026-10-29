"""Use case: spend coins on a mascot."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.mascot import MascotsOutputDTO
from src.application.ports.coin_repository import CoinRepositoryProtocol
from src.application.ports.mascot_repository import MascotRepositoryProtocol
from src.application.use_cases.get_mascots import GetMascotsUseCase
from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.enums import CoinReason
from src.domain.exceptions import (
    InsufficientCoinsException,
    MascotAlreadyOwnedException,
    MascotNotFoundException,
)


@dataclass
class PurchaseMascotUseCase:
    coins: CoinRepositoryProtocol
    mascots: MascotRepositoryProtocol

    async def execute(self, user_id: int, mascot_id: str) -> MascotsOutputDTO:
        # Locks the user's row, so one user's purchases are serialised.
        balance = await self.coins.balance(user_id, for_update=True)
        mascot = await self.mascots.get_active(mascot_id)
        if mascot is None:
            raise MascotNotFoundException(f"no mascot {mascot_id!r}")
        if mascot.coin_cost == 0 or mascot_id in await self.mascots.owned_ids(user_id):
            raise MascotAlreadyOwnedException(f"mascot {mascot_id!r} is already yours")
        if balance < mascot.coin_cost:
            raise InsufficientCoinsException(f"need {mascot.coin_cost} coins, have {balance}")
        await self.mascots.add_owned(user_id, mascot_id)
        await self.coins.add(CoinTransaction.create(user_id, -mascot.coin_cost, CoinReason.SPEND))
        return await GetMascotsUseCase(self.coins, self.mascots).execute(user_id)
