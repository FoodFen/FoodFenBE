"""Use case: the Premium-days bundles a user can buy with coins."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.coin import CoinBundleOutputDTO
from src.application.ports.coin_bundle_repository import CoinBundleRepositoryProtocol


@dataclass
class ListCoinBundlesUseCase:
    bundles: CoinBundleRepositoryProtocol

    async def execute(self) -> list[CoinBundleOutputDTO]:
        return [
            CoinBundleOutputDTO(id=b.id, days=b.days, coin_cost=b.coin_cost)
            for b in await self.bundles.list_active()
        ]
