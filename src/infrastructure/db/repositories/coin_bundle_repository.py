"""Concrete ``CoinBundleRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.coin_bundle import CoinBundle
from src.infrastructure.db.models.coin_bundle_model import CoinBundleORM


class SQLAlchemyCoinBundleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[CoinBundle]:
        rows = (
            await self._session.execute(
                select(CoinBundleORM).where(CoinBundleORM.active.is_(True)).order_by(CoinBundleORM.days)
            )
        ).scalars()
        return [row.to_domain() for row in rows]
