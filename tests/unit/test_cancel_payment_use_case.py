"""CancelPaymentUseCase unit tests. No I/O."""

from __future__ import annotations

import pytest

from src.application.use_cases.cancel_payment import CancelPaymentUseCase
from src.domain.entities.payment import Payment
from src.domain.enums import PaymentProvider, PaymentStatus, PlanType
from src.domain.exceptions import InvalidPaymentStateException, PaymentNotFoundException


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


class FakeProvider:
    def __init__(self) -> None:
        self.cancelled_with: tuple[int, str | None] | None = None

    async def create_checkout_link(self, *a, **kw):
        raise NotImplementedError

    async def get_payment_status(self, order_code):
        raise NotImplementedError

    async def cancel(self, order_code, reason):
        self.cancelled_with = (order_code, reason)

    def verify_webhook(self, raw_body):
        raise NotImplementedError


async def test_cancels_a_pending_payment():
    payments = FakePaymentRepo()
    payments.seed(Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1)
    provider = FakeProvider()
    use_case = CancelPaymentUseCase(payments=payments, providers={PaymentProvider.PAYOS: provider})

    result = await use_case.execute(user_id=1, order_code=1, reason="changed my mind")

    assert result.status is PaymentStatus.CANCELLED
    assert provider.cancelled_with == (1, "changed my mind")


async def test_rejects_cancelling_an_already_paid_payment():
    payments = FakePaymentRepo()
    payment = payments.seed(
        Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1
    )
    payment.mark_paid()
    use_case = CancelPaymentUseCase(payments=payments, providers={PaymentProvider.PAYOS: FakeProvider()})

    with pytest.raises(InvalidPaymentStateException):
        await use_case.execute(user_id=1, order_code=1, reason=None)


async def test_raises_not_found_for_another_users_payment():
    payments = FakePaymentRepo()
    payments.seed(Payment.create(user_id=2, plan_type=PlanType.MONTHLY, amount="49000"), order_code=1)
    use_case = CancelPaymentUseCase(payments=payments, providers={PaymentProvider.PAYOS: FakeProvider()})

    with pytest.raises(PaymentNotFoundException):
        await use_case.execute(user_id=1, order_code=1, reason=None)
