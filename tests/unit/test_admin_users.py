"""Effective-premium and shown-streak rules, and ListAdminUsersUseCase filtering + paging. No I/O."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from src.application.account_status import is_premium_today, shown_streak
from src.application.use_cases.list_admin_users import ListAdminUsersUseCase
from src.domain.entities.streak import Streak
from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User
from src.domain.enums import PlanType, SubscriptionStatus, SubscriptionTier

TODAY = date(2026, 10, 10)


def _user(id_: int, email: str, name: str | None = None, *, premium: bool = False, age_days: int = 0) -> User:
    return User(
        id=id_, email=email, name=name,
        subscription_tier=SubscriptionTier.PREMIUM if premium else SubscriptionTier.FREE,
        created_at=datetime(2026, 10, 1, tzinfo=UTC) - timedelta(days=age_days),
    )


def _sub(end: date | None) -> Subscription:
    return Subscription.create(1, PlanType.MONTHLY, date(2026, 9, 1), end, 99000)


def _streak(current: int, last: date | None) -> Streak:
    return Streak(id=Streak.create(1).id, user_id=1, current_streak=current, longest_streak=current, last_active_date=last)


def test_premium_needs_flag_and_a_covering_or_missing_subscription():
    premium, free = _user(1, "a@x.co", premium=True), _user(2, "b@x.co")
    assert is_premium_today(premium, _sub(date(2026, 10, 10)), TODAY)
    assert not is_premium_today(premium, _sub(date(2026, 10, 9)), TODAY)  # lapsed
    assert is_premium_today(premium, None, TODAY)  # flag set by hand, no subscription row
    assert not is_premium_today(free, _sub(date(2026, 12, 1)), TODAY)
    assert not is_premium_today(free, None, TODAY)


def test_streak_shown_only_if_active_today_or_yesterday():
    assert shown_streak(_streak(5, TODAY), TODAY) == 5
    assert shown_streak(_streak(5, TODAY - timedelta(days=1)), TODAY) == 5
    assert shown_streak(_streak(5, TODAY - timedelta(days=2)), TODAY) == 0
    assert shown_streak(_streak(0, None), TODAY) == 0
    assert shown_streak(None, TODAY) == 0


class FakeStats:
    def __init__(self, accounts):
        self._accounts = accounts

    async def accounts(self):
        return self._accounts


def _accounts():
    return [
        (_user(1, "an@x.co", "Nguyễn Văn Ân", age_days=3), None, None),
        (_user(2, "binh@x.co", None, premium=True, age_days=2), _sub(date(2026, 10, 20)), _streak(4, TODAY)),
        (_user(3, "cuong@x.co", "Cường", premium=True, age_days=1), _sub(date(2026, 9, 30)), None),  # lapsed
        (_user(4, "dung@x.co", "Dũng", age_days=1), None, None),  # same created_at as 3: id desc
    ]


async def _run(**kw):
    args = dict(q=None, tier=None, offset=0, limit=20, today=TODAY) | kw
    return await ListAdminUsersUseCase(FakeStats(_accounts())).execute(**args)


async def test_order_is_newest_first_then_id_desc_and_rows_are_derived():
    page = await _run()
    assert [u.id for u in page.users] == [4, 3, 2, 1]
    assert page.total == 4 and page.next_cursor is None
    by_id = {u.id: u for u in page.users}
    assert (by_id[2].tier, by_id[2].streak, by_id[2].display_name) == (SubscriptionTier.PREMIUM, 4, None)
    assert (by_id[3].tier, by_id[3].streak) == (SubscriptionTier.FREE, 0)  # lapsed counts as free


async def test_q_matches_name_or_email_ignoring_case_and_diacritics():
    assert [u.id for u in (await _run(q="nguyen van an")).users] == [1]  # name, diacritics
    assert [u.id for u in (await _run(q="CUONG")).users] == [3]  # name "Cường" and email
    assert [u.id for u in (await _run(q="binh@")).users] == [2]  # email, user has no name
    assert (await _run(q="   ")).total == 4  # blank = none
    assert (await _run(q="zzz")).users == []


async def test_tier_filters_on_effective_tier():
    assert [u.id for u in (await _run(tier=SubscriptionTier.PREMIUM)).users] == [2]
    assert [u.id for u in (await _run(tier=SubscriptionTier.FREE)).users] == [4, 3, 1]


async def test_paging_total_and_cursor():
    first = await _run(limit=3)
    assert ([u.id for u in first.users], first.total, first.next_cursor) == ([4, 3, 2], 4, "3")
    last = await _run(limit=3, offset=3)
    assert ([u.id for u in last.users], last.total, last.next_cursor) == ([1], 4, None)
    exact = await _run(limit=2, offset=2)
    assert exact.next_cursor is None  # nothing after the last row
