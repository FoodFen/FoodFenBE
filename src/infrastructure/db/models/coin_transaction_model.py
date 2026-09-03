"""ORM model for the coin ledger."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.enums import CoinReason
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class CoinTransactionORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "coin_transactions"
    __table_args__ = (Index("ix_coin_transactions_user_created_at", "user_id", "created_at"),)

    # Signed: positive credits, negative debits. Balance = SUM(amount).
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[CoinReason] = mapped_column(
        enum_column(CoinReason, "coin_reason"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_domain(self) -> CoinTransaction:
        return CoinTransaction(
            id=self.id,
            user_id=self.user_id,
            amount=self.amount,
            reason=self.reason,
            created_at=self.created_at,
        )

    @staticmethod
    def from_domain(transaction: CoinTransaction) -> CoinTransactionORM:
        return CoinTransactionORM(
            id=transaction.id,
            user_id=transaction.user_id,
            amount=transaction.amount,
            reason=transaction.reason,
            created_at=transaction.created_at,
        )
