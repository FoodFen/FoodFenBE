"""PayOsPaymentProvider unit tests: fake SDK client, no network."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from src.domain.enums import PaymentStatus
from src.domain.exceptions import InvalidWebhookSignatureException
from src.infrastructure.payments.payos_provider import PayOsPaymentProvider


@dataclass
class _CreateResponse:
    payment_link_id: str
    checkout_url: str
    qr_code: str


@dataclass
class _StatusResponse:
    status: str


@dataclass
class _WebhookData:
    order_code: int
    code: str


class _FakePaymentRequests:
    def __init__(self) -> None:
        self.create_called_with = None
        self.cancel_called_with = None

    async def create(self, payment_data):
        self.create_called_with = payment_data
        return _CreateResponse(
            payment_link_id="link-1", checkout_url="https://pay.example/1", qr_code="qr"
        )

    async def get(self, id):
        return _StatusResponse(status="PAID")

    async def cancel(self, id, cancellation_reason=None):
        self.cancel_called_with = (id, cancellation_reason)


class _FakeWebhooks:
    def __init__(self, result=None, raises: bool = False):
        self._result = result
        self._raises = raises

    def verify(self, payload):
        if self._raises:
            import payos

            raise payos.InvalidSignatureError("checksum mismatch")
        return self._result


class _FakeClient:
    def __init__(self, webhooks_result=None, webhooks_raises=False):
        self.payment_requests = _FakePaymentRequests()
        self.webhooks = _FakeWebhooks(webhooks_result, webhooks_raises)


async def test_create_checkout_link_translates_response():
    client = _FakeClient()
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    result = await provider.create_checkout_link(
        order_code=1,
        amount=Decimal("49000"),
        description="desc",
        cancel_url="https://a/cancel",
        return_url="https://a/return",
    )

    assert result.checkout_url == "https://pay.example/1"
    assert result.qr_code == "qr"


async def test_get_payment_status_maps_paid():
    client = _FakeClient()
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    result = await provider.get_payment_status(order_code=1)

    assert result.status is PaymentStatus.PAID
    assert result.succeeded is True


async def test_cancel_passes_order_code_and_reason():
    client = _FakeClient()
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    await provider.cancel(order_code=1, reason="changed mind")

    assert client.payment_requests.cancel_called_with == (1, "changed mind")


async def test_verify_webhook_translates_success_payload():
    client = _FakeClient(webhooks_result=_WebhookData(order_code=42, code="00"))
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    payload = provider.verify_webhook(b"raw")

    assert payload.order_code == 42
    assert payload.succeeded is True


async def test_verify_webhook_translates_failure_payload():
    client = _FakeClient(webhooks_result=_WebhookData(order_code=42, code="01"))
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    payload = provider.verify_webhook(b"raw")

    assert payload.succeeded is False


async def test_verify_webhook_raises_on_bad_signature():
    client = _FakeClient(webhooks_raises=True)
    provider = PayOsPaymentProvider(client=client, checksum_key="key")

    with pytest.raises(InvalidWebhookSignatureException):
        provider.verify_webhook(b"raw")
