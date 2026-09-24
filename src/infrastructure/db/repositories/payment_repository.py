"""Concrete ``PaymentRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.payment import Payment
from src.domain.exceptions import PaymentNotFoundException
from src.infrastructure.db.models.payment_model import PaymentORM


class SQLAlchemyPaymentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, payment: Payment) -> Payment:
        row = PaymentORM.from_domain(payment)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()

    async def get_by_order_code(self, order_code: int) -> Payment | None:
        row = (
            await self._session.execute(
                select(PaymentORM).where(PaymentORM.order_code == order_code)
            )
        ).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def update(self, payment: Payment) -> Payment:
        row = await self._session.get(PaymentORM, payment.id)
        if row is None:
            raise PaymentNotFoundException(f"payment {payment.id} not found")
        fresh = PaymentORM.from_domain(payment)
        for column in PaymentORM.__table__.columns.keys():
            if column == "order_code":
                continue  # identity column: never overwritten after insert
            setattr(row, column, getattr(fresh, column))
        await self._session.flush()
        return row.to_domain()
