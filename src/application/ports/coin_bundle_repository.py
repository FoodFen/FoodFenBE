"""Persistence port for the coin-redeemable Premium bundles."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.coin_bundle import CoinBundle


class CoinBundleRepositoryProtocol(Protocol):
    async def list_active(self) -> list[CoinBundle]:
        """Redeemable bundles, fewest days first."""
        ...
