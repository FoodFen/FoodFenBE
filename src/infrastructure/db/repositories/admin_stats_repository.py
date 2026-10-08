"""Concrete ``AdminStatsRepositoryProtocol``: three plain range selects."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import PaymentStatus
from src.infrastructure.db.models.payment_model import PaymentORM
from src.infrastructure.db.models.restaurant_model import RestaurantORM
from src.infrastructure.db.models.user_model import UserORM


class SQLAlchemyAdminStatsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def paid_payments(self, start: datetime, end: datetime) -> list[tuple[datetime, Decimal]]:
        rows = await self._session.execute(
            select(PaymentORM.paid_at, PaymentORM.amount).where(
                PaymentORM.status == PaymentStatus.PAID,
                PaymentORM.paid_at >= start,
                PaymentORM.paid_at < end,
            )
        )
        return [(paid_at, amount) for paid_at, amount in rows.all()]

    async def user_signups(self, start: datetime, end: datetime) -> list[datetime]:
        return list(
            (await self._session.execute(
                select(UserORM.created_at).where(UserORM.created_at >= start, UserORM.created_at < end)
            )).scalars()
        )

    async def restaurant_signups(self, start: datetime, end: datetime) -> list[datetime]:
        return list(
            (await self._session.execute(
                select(RestaurantORM.created_at).where(
                    RestaurantORM.created_at >= start, RestaurantORM.created_at < end
                )
            )).scalars()
        )
