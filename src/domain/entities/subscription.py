"""Subscription entity — one row per user, gating Premium features."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from src.domain.enums import PlanType, SubscriptionStatus
from src.domain.validation import require_non_negative, require_not_before


@dataclass
class Subscription:
    """A paid plan.

    ``price`` is ``Decimal``, not ``float``: the ERD says float, but binary
    floats cannot represent 9.99 exactly and the error compounds across renewals
    and refunds. Stored as NUMERIC(10, 2).
    """

    id: UUID
    user_id: UUID
    plan_type: PlanType
    status: SubscriptionStatus
    start_date: date
    end_date: date
    price: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.price, Decimal):
            # Accept ints/strings at the boundary, but never a float — converting
            # a float here would bake in the very rounding error we are avoiding.
            self.price = Decimal(str(self.price))
        require_non_negative(self.price, "price")
        require_not_before(self.end_date, self.start_date, "end_date", "start_date")

    @property
    def is_active_on(self) -> bool:
        return self.status is SubscriptionStatus.ACTIVE

    def covers(self, day: date) -> bool:
        """Whether this subscription grants Premium access on ``day``."""
        return self.is_active_on and self.start_date <= day <= self.end_date

    @classmethod
    def create(
        cls,
        user_id: UUID,
        plan_type: PlanType,
        start_date: date,
        end_date: date,
        price: Decimal | int | str,
        status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    ) -> Subscription:
        return cls(
            id=uuid4(),
            user_id=user_id,
            plan_type=plan_type,
            status=status,
            start_date=start_date,
            end_date=end_date,
            price=Decimal(str(price)),
        )
