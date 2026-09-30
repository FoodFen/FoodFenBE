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
    assert sub.start_date == date(2026, 1, 1)  # still running today, not a future-dated period
    assert sub.end_date == date(2026, 3, 2)
    assert sub.id == existing.id
    assert sub.covers(date(2026, 1, 20))  # regression: early renewal used to lapse the user at once


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


def test_grant_days_from_none_gives_exactly_n_days_today():
    sub = Subscription.grant_days(None, user_id=1, days=10, today=date(2026, 1, 1))
    assert (sub.plan_type, sub.price) == (PlanType.COIN_REDEEM, Decimal(0))
    assert (sub.start_date, sub.end_date) == (date(2026, 1, 1), date(2026, 1, 10))
    assert sub.covers(date(2026, 1, 10)) and not sub.covers(date(2026, 1, 11))


def test_grant_days_extends_a_running_subscription_keeping_plan_and_price():
    paid = Subscription.renew(None, 1, PlanType.MONTHLY, "49000", date(2026, 1, 1))
    sub = Subscription.grant_days(paid, user_id=1, days=30, today=date(2026, 1, 20))
    assert sub.end_date == date(2026, 3, 3)
    assert (sub.plan_type, sub.price, sub.start_date) == (PlanType.MONTHLY, Decimal("49000"), date(2026, 1, 1))
    assert sub.covers(date(2026, 1, 20))
    assert paid.end_date == date(2026, 2, 1)  # input not mutated


def test_grant_days_on_a_lapsed_subscription_restarts_today_on_the_same_row():
    lapsed = Subscription.renew(None, 1, PlanType.MONTHLY, "49000", date(2026, 1, 1))
    lapsed.status = SubscriptionStatus.EXPIRED
    sub = Subscription.grant_days(lapsed, user_id=1, days=10, today=date(2026, 6, 1))
    assert (sub.id, sub.plan_type, sub.start_date) == (lapsed.id, PlanType.COIN_REDEEM, date(2026, 6, 1))
    assert sub.covers(date(2026, 6, 1))
