"""ORM model for subscriptions — at most one row per user."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.subscription import Subscription
from src.domain.enums import PlanType, SubscriptionStatus
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class SubscriptionORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "subscriptions"
    # The ERD's USER ||--o| SUBSCRIPTION: zero or one.
    __table_args__ = (UniqueConstraint("user_id", name="uq_subscriptions_user"),)

    plan_type: Mapped[PlanType] = mapped_column(enum_column(PlanType, "plan_type"), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        enum_column(SubscriptionStatus, "subscription_status"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # NUMERIC, not float: money must round-trip exactly.
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    def to_domain(self) -> Subscription:
        return Subscription(
            id=self.id,
            user_id=self.user_id,
            plan_type=self.plan_type,
            status=self.status,
            start_date=self.start_date,
            end_date=self.end_date,
            price=self.price,
        )

    @staticmethod
    def from_domain(subscription: Subscription) -> SubscriptionORM:
        return SubscriptionORM(
            id=subscription.id,
            user_id=subscription.user_id,
            plan_type=subscription.plan_type,
            status=subscription.status,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
            price=subscription.price,
        )
