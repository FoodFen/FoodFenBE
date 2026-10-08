"""GetAdminDashboardUseCase: Vietnam-day bucketing, zero-fill, range rules. No I/O."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from src.application.use_cases.get_admin_dashboard import GetAdminDashboardUseCase
from src.domain.exceptions import InvalidAttributeException

TODAY = date(2026, 10, 8)


class FakeStats:
    def __init__(self, payments=(), users=(), restaurants=()):
        self.payments, self.users, self.restaurants = list(payments), list(users), list(restaurants)
        self.ranges: list[tuple[datetime, datetime]] = []

    async def paid_payments(self, start, end):
        self.ranges.append((start, end))
        return [(t, a) for t, a in self.payments if start <= t < end]

    async def user_signups(self, start, end):
        return [t for t in self.users if start <= t < end]

    async def restaurant_signups(self, start, end):
        return [t for t in self.restaurants if start <= t < end]


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
