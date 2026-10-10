"""GetAdminDashboardUseCase: Vietnam-day bucketing, zero-fill, range rules. No I/O."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from src.application.use_cases.get_admin_dashboard import GetAdminDashboardUseCase
from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User
from src.domain.enums import PlanType, SubscriptionTier
from src.domain.exceptions import InvalidAttributeException

TODAY = date(2026, 10, 8)


class FakeStats:
    def __init__(self, payments=(), users=(), restaurants=(), food_days=(), accounts=()):
        self.payments, self.users, self.restaurants = list(payments), list(users), list(restaurants)
        self.food_days, self._accounts = list(food_days), list(accounts)
        self.ranges: list[tuple[datetime, datetime]] = []

    async def paid_payments(self, start, end):
        self.ranges.append((start, end))
        return [(t, a) for t, a in self.payments if start <= t < end]

    async def user_signups(self, start, end):
        return [t for t in self.users if start <= t < end]

    async def restaurant_signups(self, start, end):
        return [t for t in self.restaurants if start <= t < end]

    async def food_entry_days(self, first, last):
        return [d for d in self.food_days if first <= d <= last]

    async def accounts(self):
        return self._accounts


async def test_bucketing_uses_vietnam_day_boundary():
    stats = FakeStats(payments=[
        (datetime(2026, 10, 7, 16, 59, tzinfo=UTC), Decimal("99000")),   # 23:59 VN on Oct 7
        (datetime(2026, 10, 7, 17, 0, tzinfo=UTC), Decimal("990000")),   # 00:00 VN on Oct 8
    ])
    result = await GetAdminDashboardUseCase(stats).execute(date(2026, 10, 7), date(2026, 10, 8), TODAY)
    assert [(d.date, d.premium_revenue) for d in result.daily] == [
        (date(2026, 10, 7), 99000), (date(2026, 10, 8), 990000),
    ]
    assert result.premium_revenue == 1089000 and isinstance(result.premium_revenue, int)


async def test_series_is_zero_filled_and_counts_signups():
    stats = FakeStats(
        users=[datetime(2026, 10, 2, 3, tzinfo=UTC)] * 2,
        restaurants=[datetime(2026, 10, 3, 3, tzinfo=UTC)],
    )
    result = await GetAdminDashboardUseCase(stats).execute(date(2026, 10, 1), date(2026, 10, 3), TODAY)
    assert [(d.date.day, d.new_users, d.new_restaurants, d.ad_revenue) for d in result.daily] == [
        (1, 0, 0, 0), (2, 2, 0, 0), (3, 0, 1, 0),
    ]
    assert (result.new_users, result.new_restaurants, result.ad_revenue) == (2, 1, 0)


async def test_default_range_is_last_30_vietnam_days():
    stats = FakeStats()
    result = await GetAdminDashboardUseCase(stats).execute(None, None, TODAY)
    assert (result.from_date, result.to_date, len(result.daily)) == (date(2026, 9, 9), TODAY, 30)
    assert stats.ranges == [(
        datetime(2026, 9, 8, 17, tzinfo=UTC), datetime(2026, 10, 8, 17, tzinfo=UTC),
    )]


async def test_range_rules():
    use_case = GetAdminDashboardUseCase(FakeStats())
    with pytest.raises(InvalidAttributeException):
        await use_case.execute(date(2026, 10, 9), date(2026, 10, 8), TODAY)
    with pytest.raises(InvalidAttributeException):
        await use_case.execute(date(2025, 10, 7), date(2026, 10, 8), TODAY)  # 367 days
    assert len((await use_case.execute(date(2025, 10, 8), date(2026, 10, 8), TODAY)).daily) == 366


async def test_extreme_dates_are_invalid():
    use_case = GetAdminDashboardUseCase(FakeStats())
    for extreme in (date(9999, 12, 31), date(1, 1, 1)):
        with pytest.raises(InvalidAttributeException):
            await use_case.execute(extreme, extreme, TODAY)
    with pytest.raises(InvalidAttributeException):  # default from-date underflows
        await use_case.execute(None, date(1, 1, 10), TODAY)


async def test_food_entries_are_bucketed_by_logged_on_and_summed():
    stats = FakeStats(food_days=[date(2026, 10, 1)] * 3 + [date(2026, 10, 3), date(2026, 9, 30)])
    result = await GetAdminDashboardUseCase(stats).execute(date(2026, 10, 1), date(2026, 10, 3), TODAY)
    assert [d.food_entries for d in result.daily] == [3, 0, 1]
    assert result.food_entries == 4


async def test_premium_users_counts_effective_premium_today():
    def user(id_, premium):
        return User(
            id=id_, email=f"u{id_}@x.co",
            subscription_tier=SubscriptionTier.PREMIUM if premium else SubscriptionTier.FREE,
        )

    def sub(end):
        return Subscription.create(1, PlanType.MONTHLY, date(2026, 9, 1), end, 99000)

    stats = FakeStats(accounts=[
        (user(1, True), sub(date(2026, 10, 8)), None),   # covers today
        (user(2, True), sub(date(2026, 10, 7)), None),   # lapsed
        (user(3, True), None, None),                     # flag only
        (user(4, False), None, None),
    ])
    result = await GetAdminDashboardUseCase(stats).execute(date(2026, 10, 1), date(2026, 10, 3), TODAY)
    assert result.premium_users == 2  # current count, not tied to the requested range
