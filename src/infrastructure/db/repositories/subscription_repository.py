"""Concrete ``SubscriptionRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.subscription import Subscription
from src.infrastructure.db.models.subscription_model import SubscriptionORM


class SQLAlchemySubscriptionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_user_id(self, user_id: int) -> Subscription | None:
        row = (
            await self._session.execute(
                select(SubscriptionORM).where(SubscriptionORM.user_id == user_id)
            )
        ).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def save(self, subscription: Subscription) -> Subscription:
        """Upsert keyed on ``user_id`` — at most one row per user (``uq_subscriptions_user``)."""
        row = (
            await self._session.execute(
                select(SubscriptionORM).where(SubscriptionORM.user_id == subscription.user_id)
            )
        ).scalar_one_or_none()
        if row is None:
            row = SubscriptionORM.from_domain(subscription)
            self._session.add(row)
        else:
            fresh = SubscriptionORM.from_domain(subscription)
            for column in SubscriptionORM.__table__.columns.keys():
                if column == "id":
                    continue
                setattr(row, column, getattr(fresh, column))
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()
