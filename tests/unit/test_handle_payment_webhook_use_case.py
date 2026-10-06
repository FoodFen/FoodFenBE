"""HandlePaymentWebhookUseCase unit tests. No I/O — in-memory repos, scripted provider."""

from __future__ import annotations

import pytest

from src.application.ports.payment_provider import WebhookPayload
from src.application.use_cases.handle_payment_webhook import HandlePaymentWebhookUseCase
from src.domain.entities.payment import Payment
from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User
from src.domain.enums import PaymentProvider, PaymentStatus, PlanType, SubscriptionTier
from src.domain.exceptions import InvalidWebhookSignatureException, PaymentNotFoundException


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
    def __init__(self, payload: WebhookPayload | None = None, raise_invalid: bool = False) -> None:
        self._payload = payload
        self._raise_invalid = raise_invalid

    async def create_checkout_link(self, *a, **kw):
        raise NotImplementedError

    async def get_payment_status(self, order_code):
        raise NotImplementedError

    async def cancel(self, order_code, reason):
        raise NotImplementedError

    def verify_webhook(self, raw_body):
        if self._raise_invalid:
            raise InvalidWebhookSignatureException("bad signature")
        assert self._payload is not None
        return self._payload


def _user() -> User:
    user = User.create(email="a@example.com")
    user.id = 1
    return user


async def test_successful_webhook_marks_paid_creates_subscription_and_upgrades_user():
    user = _user()
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=42
    )
    subscriptions = FakeSubscriptionRepo()
    users = FakeUserRepo(user)
    provider = FakeProvider(WebhookPayload(order_code=42, status=PaymentStatus.PAID, succeeded=True))
    use_case = HandlePaymentWebhookUseCase(
        payments=payments, providers={PaymentProvider.PAYOS: provider}, subscriptions=subscriptions, users=users
    )

    await use_case.execute(PaymentProvider.PAYOS, b"raw-body")

    assert payment.status.value == "paid"
    subscription = await subscriptions.get_by_user_id(1)
    assert subscription is not None and subscription.status.value == "active"
    assert users._user.subscription_tier is SubscriptionTier.PREMIUM


async def test_failed_webhook_marks_failed_without_touching_subscription():
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=42
    )
    subscriptions = FakeSubscriptionRepo()
    provider = FakeProvider(WebhookPayload(order_code=42, status=PaymentStatus.FAILED, succeeded=False))
    use_case = HandlePaymentWebhookUseCase(
        payments=payments, providers={PaymentProvider.PAYOS: provider}, subscriptions=subscriptions, users=FakeUserRepo(_user())
    )

    await use_case.execute(PaymentProvider.PAYOS, b"raw-body")

    assert payment.status.value == "failed"
    assert await subscriptions.get_by_user_id(1) is None


async def test_pending_webhook_leaves_the_payment_pending():
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=42
    )
    subscriptions = FakeSubscriptionRepo()
    provider = FakeProvider(
        WebhookPayload(order_code=42, status=PaymentStatus.PENDING, succeeded=False)
    )
    use_case = HandlePaymentWebhookUseCase(
        payments=payments, providers={PaymentProvider.PAYOS: provider}, subscriptions=subscriptions, users=FakeUserRepo(_user())
    )

    await use_case.execute(PaymentProvider.PAYOS, b"raw-body")

    assert payment.status is PaymentStatus.PENDING
    assert await subscriptions.get_by_user_id(1) is None


async def test_success_webhook_on_a_cancelled_payment_still_grants_premium():
    user = _user()
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=42
    )
    payment.mark_cancelled()
    subscriptions = FakeSubscriptionRepo()
    users = FakeUserRepo(user)
    provider = FakeProvider(WebhookPayload(order_code=42, status=PaymentStatus.PAID, succeeded=True))
    use_case = HandlePaymentWebhookUseCase(
        payments=payments, providers={PaymentProvider.PAYOS: provider}, subscriptions=subscriptions, users=users
    )

    await use_case.execute(PaymentProvider.PAYOS, b"raw-body")

    assert payment.status.value == "paid"
    subscription = await subscriptions.get_by_user_id(1)
    assert subscription is not None and subscription.status.value == "active"
    assert users._user.subscription_tier is SubscriptionTier.PREMIUM


async def test_failure_webhook_on_a_cancelled_payment_stays_cancelled():
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=42
    )
    payment.mark_cancelled()
    provider = FakeProvider(WebhookPayload(order_code=42, status=PaymentStatus.FAILED, succeeded=False))
    use_case = HandlePaymentWebhookUseCase(
        payments=payments,
        providers={PaymentProvider.PAYOS: provider},
        subscriptions=FakeSubscriptionRepo(),
        users=FakeUserRepo(_user()),
    )

    await use_case.execute(PaymentProvider.PAYOS, b"raw-body")

    assert payment.status.value == "cancelled"


async def test_webhook_replay_is_idempotent():
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=42
    )
    provider = FakeProvider(WebhookPayload(order_code=42, status=PaymentStatus.PAID, succeeded=True))
    use_case = HandlePaymentWebhookUseCase(
        payments=payments,
        providers={PaymentProvider.PAYOS: provider},
        subscriptions=FakeSubscriptionRepo(),
        users=FakeUserRepo(_user()),
    )

    await use_case.execute(PaymentProvider.PAYOS, b"raw-body")
    first_paid_at = payment.paid_at
    await use_case.execute(PaymentProvider.PAYOS, b"raw-body")  # replay
    assert payment.paid_at == first_paid_at


async def test_invalid_signature_raises():
    provider = FakeProvider(raise_invalid=True)
    use_case = HandlePaymentWebhookUseCase(
        payments=FakePaymentRepo(),
        providers={PaymentProvider.PAYOS: provider},
        subscriptions=FakeSubscriptionRepo(),
        users=FakeUserRepo(_user()),
    )

    with pytest.raises(InvalidWebhookSignatureException):
        await use_case.execute(PaymentProvider.PAYOS, b"raw-body")


async def test_unknown_order_code_raises_not_found():
    provider = FakeProvider(WebhookPayload(order_code=999, status=PaymentStatus.PAID, succeeded=True))
    use_case = HandlePaymentWebhookUseCase(
        payments=FakePaymentRepo(),
        providers={PaymentProvider.PAYOS: provider},
        subscriptions=FakeSubscriptionRepo(),
        users=FakeUserRepo(_user()),
    )

    with pytest.raises(PaymentNotFoundException):
        await use_case.execute(PaymentProvider.PAYOS, b"raw-body")
