"""Payment entity unit tests: invariants + state transitions. Pure domain, no I/O."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.domain.entities.payment import Payment
from src.domain.enums import PaymentProvider, PaymentStatus, PlanType
from src.domain.exceptions import InvalidAttributeException, InvalidPaymentStateException


def _payment(amount="49000") -> Payment:
    return Payment.create(user_id=1, plan_type=PlanType.MONTHLY, amount=amount)


def test_create_defaults_to_pending_with_no_order_code():
    payment = _payment()
    assert payment.status is PaymentStatus.PENDING
    assert payment.order_code is None
    assert payment.amount == Decimal("49000")


def test_amount_must_be_positive():
    with pytest.raises(InvalidAttributeException):
        _payment(amount="0")


def test_attach_checkout_sets_fields_while_pending():
    payment = _payment()
    payment.attach_checkout("link-1", "https://pay.example/link-1", "qr-data")
    assert payment.payment_link_id == "link-1"
    assert payment.checkout_url == "https://pay.example/link-1"
    assert payment.qr_code == "qr-data"


def test_attach_checkout_rejects_non_pending():
    payment = _payment()
    payment.mark_paid()
    with pytest.raises(InvalidPaymentStateException):
        payment.attach_checkout("link-1", "https://pay.example/link-1", "qr-data")


def test_mark_paid_sets_status_and_paid_at():
    payment = _payment()
    payment.mark_paid()
    assert payment.status is PaymentStatus.PAID
    assert payment.paid_at is not None


def test_mark_paid_is_idempotent():
    payment = _payment()
    payment.mark_paid()
    first_paid_at = payment.paid_at
    payment.mark_paid()
    assert payment.paid_at == first_paid_at


def test_mark_cancelled_rejects_non_pending():
    payment = _payment()
    payment.mark_paid()
    with pytest.raises(InvalidPaymentStateException):
        payment.mark_cancelled()


def test_mark_cancelled_sets_status_while_pending():
    payment = _payment()
    payment.mark_cancelled()
    assert payment.status is PaymentStatus.CANCELLED


def test_create_defaults_to_payos():
    payment = Payment.create(1, PlanType.MONTHLY, 49000)
    assert payment.provider is PaymentProvider.PAYOS


def test_create_records_the_chosen_provider():
    payment = Payment.create(1, PlanType.MONTHLY, 49000, PaymentProvider.MOMO)
    assert payment.provider is PaymentProvider.MOMO


def test_attach_checkout_accepts_no_qr_code():
    payment = Payment.create(1, PlanType.MONTHLY, 49000, PaymentProvider.MOMO)
    payment.attach_checkout("FF1", "https://pay.momo/x", None)
    assert payment.qr_code is None
    assert payment.checkout_url == "https://pay.momo/x"
