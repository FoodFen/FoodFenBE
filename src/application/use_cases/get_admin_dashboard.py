"""Use case: cash flow (Premium + ads) and growth (users, restaurants) per Vietnam day.

Days are Vietnam days (UTC+7), inclusive on both ends, zero-filled so the chart has no gaps.
Ad revenue is 0 until ads exist; the field is there so the wire contract won't change.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal

from src.application.dtos.admin import DashboardDayDTO, DashboardDTO
from src.application.ports.admin_stats_repository import AdminStatsRepositoryProtocol
from src.domain.exceptions import InvalidAttributeException

VIETNAM = timezone(timedelta(hours=7))
_DEFAULT_DAYS = 30
_MAX_DAYS = 366


def _vn_day(instant: datetime) -> date:
    return instant.astimezone(VIETNAM).date()


def _vn_midnight_utc(day: date) -> datetime:
    return datetime.combine(day, time(), VIETNAM).astimezone(UTC)


@dataclass
class GetAdminDashboardUseCase:
    stats: AdminStatsRepositoryProtocol

    async def execute(
        self, from_date: date | None, to_date: date | None, today: date | None = None
    ) -> DashboardDTO:
        to_date = to_date or today or datetime.now(VIETNAM).date()
        from_date = from_date or to_date - timedelta(days=_DEFAULT_DAYS - 1)
        if from_date > to_date:
            raise InvalidAttributeException("'from' must not be after 'to'")
        span = (to_date - from_date).days + 1
        if span > _MAX_DAYS:
            raise InvalidAttributeException(f"the range must not exceed {_MAX_DAYS} days")

        start, end = _vn_midnight_utc(from_date), _vn_midnight_utc(to_date + timedelta(days=1))
        # ponytail: rows are fetched and bucketed in Python, O(rows in range) and dialect-portable.
        # Move to SQL GROUP BY when a 30-day window holds more than ~100k payments or signups.
        revenue: dict[date, Decimal] = {}
        for paid_at, amount in await self.stats.paid_payments(start, end):
            revenue[_vn_day(paid_at)] = revenue.get(_vn_day(paid_at), Decimal(0)) + amount
        users = Counter(_vn_day(t) for t in await self.stats.user_signups(start, end))
        restaurants = Counter(_vn_day(t) for t in await self.stats.restaurant_signups(start, end))

        daily = [
            DashboardDayDTO(
                date=day,
                premium_revenue=int(revenue.get(day, 0)),
                ad_revenue=0,
                new_users=users[day],
                new_restaurants=restaurants[day],
            )
            for day in (from_date + timedelta(days=i) for i in range(span))
        ]
        return DashboardDTO(
            from_date=from_date,
            to_date=to_date,
            premium_revenue=sum(d.premium_revenue for d in daily),
            ad_revenue=0,
            new_users=sum(d.new_users for d in daily),
            new_restaurants=sum(d.new_restaurants for d in daily),
            daily=daily,
        )
