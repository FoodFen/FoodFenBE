"""Concrete ``CoinRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.coin_transaction import CoinTransaction
from src.infrastructure.db.models.coin_transaction_model import CoinTransactionORM
from src.infrastructure.db.models.user_model import UserORM


class SQLAlchemyCoinRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, transaction: CoinTransaction) -> CoinTransaction:
        self._session.add(CoinTransactionORM.from_domain(transaction))
        await self._session.flush()
        return transaction

    async def balance(self, user_id: int, *, for_update: bool = False) -> int:
        if for_update:
            await self._session.execute(
                select(UserORM.id).where(UserORM.id == user_id).with_for_update()
            )
        total = await self._session.scalar(
            select(func.coalesce(func.sum(CoinTransactionORM.amount), 0)).where(
                CoinTransactionORM.user_id == user_id
            )
        )
        return int(total)
