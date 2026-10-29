"""Concrete ``CoinRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.chat_cursor import decode_cursor
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

    async def get_by_client_id(self, user_id: int, client_id: str) -> CoinTransaction | None:
        row = await self._session.scalar(
            select(CoinTransactionORM).where(
                CoinTransactionORM.user_id == user_id, CoinTransactionORM.client_id == client_id
            )
        )
        return row.to_domain() if row else None

    async def list_page(
        self, user_id: int, before: str | None, limit: int
    ) -> list[CoinTransaction]:
        query = select(CoinTransactionORM).where(CoinTransactionORM.user_id == user_id)
        if before is not None:
            query = query.where(
                tuple_(CoinTransactionORM.created_at, CoinTransactionORM.id) < decode_cursor(before)
            )
        query = query.order_by(
            CoinTransactionORM.created_at.desc(), CoinTransactionORM.id.desc()
        ).limit(limit)
        return [row.to_domain() for row in (await self._session.scalars(query))]
