"""Subscription.renew unit tests: renewal date math. Pure domain, no I/O."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.domain.entities.subscription import Subscription
from src.domain.enums import PlanType, SubscriptionStatus


def test_renew_from_none_starts_today_monthly():
    sub = Subscription.renew(
        None, user_id=1, plan_type=PlanType.MONTHLY, price="49000", today=date(2026, 1, 15)
    )
    assert sub.start_date == date(2026, 1, 15)
    assert sub.end_date == date(2026, 2, 15)
    assert sub.status is SubscriptionStatus.ACTIVE


def test_renew_monthly_clamps_end_of_month():
    sub = Subscription.renew(
        None, user_id=1, plan_type=PlanType.MONTHLY, price="49000", today=date(2026, 1, 31)
    )
    assert sub.end_date == date(2026, 2, 28)


def test_renew_annual_clamps_leap_day():
    sub = Subscription.renew(
        None, user_id=1, plan_type=PlanType.ANNUAL, price="499000", today=date(2024, 2, 29)
    )
    assert sub.end_date == date(2025, 2, 28)


def test_renew_before_expiry_stacks_from_existing_end_date():
    existing = Subscription.create(
        user_id=1,
        plan_type=PlanType.MONTHLY,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        price=Decimal("49000"),
    )
    sub = Subscription.renew(
        existing, user_id=1, plan_type=PlanType.MONTHLY, price="49000", today=date(2026, 1, 20)
    )
    assert sub.start_date == date(2026, 2, 2)
    assert sub.end_date == date(2026, 3, 2)
    assert sub.id == existing.id


def test_renew_after_expiry_starts_today_not_old_end_date():
    existing = Subscription.create(
        user_id=1,
        plan_type=PlanType.MONTHLY,
        start_date=date(2025, 1, 1),
        end_date=date(2025, 2, 1),
        price=Decimal("49000"),
    )
    sub = Subscription.renew(
        existing, user_id=1, plan_type=PlanType.ANNUAL, price="499000", today=date(2026, 1, 15)
    )
    assert sub.start_date == date(2026, 1, 15)
    assert sub.id == existing.id
