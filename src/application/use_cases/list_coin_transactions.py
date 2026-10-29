"""Use case: a page of the user's coin ledger, newest first."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.chat_cursor import encode_cursor
from src.application.dtos.coin import CoinTransactionOutputDTO, CoinTransactionsPageDTO
from src.application.ports.coin_repository import CoinRepositoryProtocol


@dataclass
class ListCoinTransactionsUseCase:
    coins: CoinRepositoryProtocol

    async def execute(self, user_id: int, before: str | None, limit: int) -> CoinTransactionsPageDTO:
        rows = await self.coins.list_page(user_id, before, limit + 1)
        page = rows[:limit]
        return CoinTransactionsPageDTO(
            transactions=[
                CoinTransactionOutputDTO(t.id, t.amount, t.reason, t.created_at) for t in page
            ],
            next_cursor=encode_cursor(page[-1]) if len(rows) > limit else None,
        )
