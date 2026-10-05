"""GetPaymentStatusUseCase unit tests. No I/O."""

from __future__ import annotations

import pytest

from src.application.ports.payment_provider import ProviderPaymentStatus
from src.application.use_cases.get_payment_status import GetPaymentStatusUseCase
from src.domain.entities.payment import Payment
from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User
from src.domain.enums import PaymentProvider, PaymentStatus, PlanType, SubscriptionTier
from src.domain.exceptions import PaymentNotFoundException


class FakePaymentRepo:
    def __init__(self) -> None:
        self._by_order_code: dict[int, Payment] = {}

    def seed(self, payment: Payment, order_code: int) -> Payment:
        payment.order_code = order_code
        self._by_order_code[order_code] = payment
        return payment

    async def create(self, payment):
        raise NotImplementedError

    async def get_by_order_code(self, order_code):
        return self._by_order_code.get(order_code)

    async def update(self, payment):
        self._by_order_code[payment.order_code] = payment
        return payment


class FakeSubscriptionRepo:
    def __init__(self) -> None:
        self._by_user_id: dict[int, Subscription] = {}

    async def get_by_user_id(self, user_id):
        return self._by_user_id.get(user_id)

    async def save(self, subscription):
        self._by_user_id[subscription.user_id] = subscription
        return subscription


class FakeUserRepo:
    def __init__(self, user: User) -> None:
        self._user = user

    async def get_by_id(self, user_id):
        return self._user if user_id == self._user.id else None

    async def get_by_email(self, email):
        raise NotImplementedError

    async def create(self, user):
        raise NotImplementedError

    async def update(self, user):
        self._user = user
        return user


class FakeProvider:
    def __init__(self, provider_status: ProviderPaymentStatus) -> None:
        self._status = provider_status

    async def create_checkout_link(self, *a, **kw):
        raise NotImplementedError

    async def get_payment_status(self, order_code):
        return self._status

    async def cancel(self, order_code, reason):
        raise NotImplementedError

    def verify_webhook(self, raw_body):
        raise NotImplementedError


def _user() -> User:
    user = User.create(email="a@example.com")
    user.id = 1
    return user


async def test_returns_local_status_without_reconciling_when_not_pending():
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1
    )
    payment.mark_paid()
    provider = FakeProvider(ProviderPaymentStatus(order_code=1, status=PaymentStatus.PAID, succeeded=True))
    use_case = GetPaymentStatusUseCase(
        payments=payments, providers={PaymentProvider.PAYOS: provider}, subscriptions=FakeSubscriptionRepo(), users=FakeUserRepo(_user())
    )
    result = await use_case.execute(user_id=1, order_code=1)
    assert result.status is PaymentStatus.PAID


async def test_reconciles_pending_payment_when_provider_reports_paid():
    user = _user()
    payments = FakePaymentRepo()
    payments.seed(Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1)
    provider = FakeProvider(ProviderPaymentStatus(order_code=1, status=PaymentStatus.PAID, succeeded=True))
    users = FakeUserRepo(user)
    use_case = GetPaymentStatusUseCase(
        payments=payments, providers={PaymentProvider.PAYOS: provider}, subscriptions=FakeSubscriptionRepo(), users=users
    )
    result = await use_case.execute(user_id=1, order_code=1)
    assert result.status is PaymentStatus.PAID
    assert users._user.subscription_tier is SubscriptionTier.PREMIUM


async def test_reconciles_cancelled_payment_when_provider_reports_paid():
    user = _user()
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1
    )
    payment.mark_cancelled()
    provider = FakeProvider(ProviderPaymentStatus(order_code=1, status=PaymentStatus.PAID, succeeded=True))
    users = FakeUserRepo(user)
    use_case = GetPaymentStatusUseCase(
        payments=payments, providers={PaymentProvider.PAYOS: provider}, subscriptions=FakeSubscriptionRepo(), users=users
    )
    result = await use_case.execute(user_id=1, order_code=1)
    assert result.status is PaymentStatus.PAID
    assert users._user.subscription_tier is SubscriptionTier.PREMIUM


async def test_raises_not_found_for_another_users_payment():
    payments = FakePaymentRepo()
    payments.seed(Payment.create(user_id=2, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1)
    provider = FakeProvider(ProviderPaymentStatus(order_code=1, status=PaymentStatus.PENDING, succeeded=False))
    use_case = GetPaymentStatusUseCase(
        payments=payments, providers={PaymentProvider.PAYOS: provider}, subscriptions=FakeSubscriptionRepo(), users=FakeUserRepo(_user())
    )
    with pytest.raises(PaymentNotFoundException):
        await use_case.execute(user_id=1, order_code=1)
