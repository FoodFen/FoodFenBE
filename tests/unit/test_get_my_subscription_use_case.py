"""GetMySubscriptionUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.application.use_cases.get_my_subscription import GetMySubscriptionUseCase
from src.domain.entities.subscription import Subscription
from src.domain.enums import PlanType


class FakeSubscriptionRepo:
    def __init__(self, subscription: Subscription | None = None) -> None:
        self._subscription = subscription

    async def get_by_user_id(self, user_id):
        return self._subscription

    async def save(self, subscription):
        raise NotImplementedError


async def test_returns_none_when_no_subscription():
    use_case = GetMySubscriptionUseCase(subscriptions=FakeSubscriptionRepo(None))
    assert await use_case.execute(1) is None


async def test_returns_dto_when_subscription_exists():
    sub = Subscription.create(
        user_id=1,
        plan_type=PlanType.MONTHLY,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        price=Decimal("49000"),
    )
    use_case = GetMySubscriptionUseCase(subscriptions=FakeSubscriptionRepo(sub))
    result = await use_case.execute(1)
    assert result is not None
    assert result.plan_type is PlanType.MONTHLY
