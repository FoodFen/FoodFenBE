"""Concrete ``AdminStatsRepositoryProtocol``: plain selects, bucketing is the use case's job."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.streak import Streak
from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User
from src.domain.enums import PaymentStatus
from src.infrastructure.db.models.food_entry_model import FoodEntryORM
from src.infrastructure.db.models.payment_model import PaymentORM
from src.infrastructure.db.models.restaurant_model import RestaurantORM
from src.infrastructure.db.models.streak_model import StreakORM
from src.infrastructure.db.models.subscription_model import SubscriptionORM
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

    async def food_entry_days(self, first: date, last: date) -> list[date]:
        return list(
            (await self._session.execute(
                select(FoodEntryORM.logged_on).where(
                    FoodEntryORM.deleted_at.is_(None),
                    FoodEntryORM.logged_on >= first,
                    FoodEntryORM.logged_on <= last,
                )
            )).scalars()
        )

    async def accounts(self) -> list[tuple[User, Subscription | None, Streak | None]]:
        rows = await self._session.execute(
            select(UserORM, SubscriptionORM, StreakORM)
            .outerjoin(SubscriptionORM, SubscriptionORM.user_id == UserORM.id)
            .outerjoin(StreakORM, StreakORM.user_id == UserORM.id)
        )
        return [(u.to_domain(), s and s.to_domain(), k and k.to_domain()) for u, s, k in rows.all()]
