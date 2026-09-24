"""CreateCheckoutUseCase unit tests: in-memory repo + scripted provider. No I/O."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.application.dtos.payment import CreateCheckoutInputDTO
from src.application.ports.payment_provider import CheckoutLinkResult
from src.application.use_cases.create_checkout import CreateCheckoutUseCase
from src.domain.entities.payment import Payment
from src.domain.enums import PaymentStatus, PlanType
from src.domain.exceptions import PaymentNotFoundException


class FakePaymentRepo:
    def __init__(self) -> None:
        self._by_order_code: dict[int, Payment] = {}
        self._next_order_code = 1000

    async def create(self, payment: Payment) -> Payment:
        payment.order_code = self._next_order_code
        self._next_order_code += 1
        self._by_order_code[payment.order_code] = payment
        return payment

    async def get_by_order_code(self, order_code: int) -> Payment | None:
        return self._by_order_code.get(order_code)

    async def update(self, payment: Payment) -> Payment:
        if payment.order_code not in self._by_order_code:
            raise PaymentNotFoundException(str(payment.order_code))
        self._by_order_code[payment.order_code] = payment
        return payment


class FakePaymentProvider:
    def __init__(self) -> None:
        self.created_with: dict | None = None

    async def create_checkout_link(self, order_code, amount, description, cancel_url, return_url):
        self.created_with = {
            "order_code": order_code,
            "amount": amount,
            "description": description,
            "cancel_url": cancel_url,
            "return_url": return_url,
        }
        return CheckoutLinkResult(
            payment_link_id=f"link-{order_code}",
            checkout_url=f"https://pay.example/{order_code}",
            qr_code="qr-data",
        )

    async def get_payment_status(self, order_code):
        raise NotImplementedError

    async def cancel(self, order_code, reason):
        raise NotImplementedError

    def verify_webhook(self, raw_body):
        raise NotImplementedError


@pytest.fixture
def use_case() -> CreateCheckoutUseCase:
    return CreateCheckoutUseCase(
        payments=FakePaymentRepo(),
        provider=FakePaymentProvider(),
        monthly_price_vnd=49_000,
        annual_price_vnd=499_000,
        return_url="https://app.example/return",
        cancel_url="https://app.example/cancel",
    )


async def test_execute_creates_pending_payment_then_attaches_checkout(use_case):
    result = await use_case.execute(CreateCheckoutInputDTO(user_id=1, plan_type=PlanType.MONTHLY))
    assert result.status is PaymentStatus.PENDING
    assert result.amount == Decimal("49000")
    assert result.checkout_url == f"https://pay.example/{result.order_code}"
    assert result.qr_code == "qr-data"


async def test_execute_prices_annual_plan_separately(use_case):
    result = await use_case.execute(CreateCheckoutInputDTO(user_id=1, plan_type=PlanType.ANNUAL))
    assert result.amount == Decimal("499000")


async def test_execute_passes_order_code_and_amount_to_provider(use_case):
    result = await use_case.execute(CreateCheckoutInputDTO(user_id=1, plan_type=PlanType.MONTHLY))
    assert use_case.provider.created_with["order_code"] == result.order_code
    assert use_case.provider.created_with["amount"] == Decimal("49000")
