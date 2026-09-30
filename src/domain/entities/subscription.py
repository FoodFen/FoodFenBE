"""Subscription entity — one row per user, gating Premium features."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, replace
from datetime import date, timedelta
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
    user_id: int
    plan_type: PlanType
    status: SubscriptionStatus
    start_date: date
    # None means an auto-renewing plan with no fixed end.
    end_date: date | None
    price: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.price, Decimal):
            # Accept ints/strings at the boundary, but never a float — converting
            # a float here would bake in the very rounding error we are avoiding.
            self.price = Decimal(str(self.price))
        require_non_negative(self.price, "price")
        if self.end_date is not None:
            require_not_before(self.end_date, self.start_date, "end_date", "start_date")

    @property
    def is_active_on(self) -> bool:
        return self.status is SubscriptionStatus.ACTIVE

    def covers(self, day: date) -> bool:
        """Whether this subscription grants Premium access on ``day``."""
        if not self.is_active_on or day < self.start_date:
            return False
        return self.end_date is None or day <= self.end_date

    @classmethod
    def create(
        cls,
        user_id: int,
        plan_type: PlanType,
        start_date: date,
        end_date: date | None,
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

    @classmethod
    def renew(
        cls,
        existing: Subscription | None,
        user_id: int,
        plan_type: PlanType,
        price: Decimal | int | str,
        today: date,
    ) -> Subscription:
        """Extend or start a subscription. An early renewal (before ``existing``
        expires) stacks the new period after the current one instead of
        wasting the days already paid for."""
        running = existing is not None and existing.end_date is not None and existing.end_date >= today
        # The new period stacks after the old one, but ``start_date`` must stay in the
        # past: ``covers`` is false before it, so a future start would lapse the user today.
        period_start = existing.end_date + timedelta(days=1) if running else today
        return cls(
            id=existing.id if existing is not None else uuid4(),
            user_id=user_id,
            plan_type=plan_type,
            status=SubscriptionStatus.ACTIVE,
            start_date=existing.start_date if running else today,
            end_date=_add_period(period_start, plan_type),
            price=Decimal(str(price)),
        )

    @classmethod
    def grant_days(
        cls, existing: Subscription | None, user_id: int, days: int, today: date
    ) -> Subscription:
        """Add ``days`` of Premium. While ``existing`` still runs, extend its end date
        in place (keeping its plan and price); otherwise start a free coin-funded
        period today."""
        if existing is not None and existing.end_date is not None and existing.end_date >= today:
            return replace(
                existing,
                status=SubscriptionStatus.ACTIVE,
                end_date=existing.end_date + timedelta(days=days),
            )
        return cls(
            id=existing.id if existing is not None else uuid4(),
            user_id=user_id,
            plan_type=PlanType.COIN_REDEEM,
            status=SubscriptionStatus.ACTIVE,
            start_date=today,
            end_date=today + timedelta(days=days - 1),
            price=Decimal(0),
        )


def _add_period(start: date, plan_type: PlanType) -> date:
    if plan_type is PlanType.ANNUAL:
        try:
            return start.replace(year=start.year + 1)
        except ValueError:
            # Feb 29 in a source year, but the target year isn't a leap year.
            return start.replace(year=start.year + 1, day=28)
    month = start.month % 12 + 1
    year = start.year + (start.month // 12)
    last_day = calendar.monthrange(year, month)[1]
    return start.replace(year=year, month=month, day=min(start.day, last_day))
