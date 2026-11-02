"""Persistence port for the coin ledger."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.coin_transaction import CoinTransaction


class CoinRepositoryProtocol(Protocol):
    async def add(self, transaction: CoinTransaction) -> CoinTransaction: ...

    async def balance(self, user_id: int, *, for_update: bool = False) -> int:
        """Sum of the user's ledger. ``for_update`` serialises concurrent spenders
        (locks the user's row until the transaction ends) — take it before a check-then-debit."""
        ...

    async def get_by_client_id(self, user_id: int, client_id: str) -> CoinTransaction | None: ...

    async def list_page(
        self, user_id: int, before: str | None, limit: int
    ) -> list[CoinTransaction]:
        """Newest first by ``(created_at, id)``; ``before`` is a ``chat_cursor`` cursor."""
        ...
