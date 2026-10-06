"""PayOS adapter: implements PaymentProviderProtocol by wrapping the official
`payos` SDK's async client (`payos.AsyncPayOS`).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import payos

from src.application.ports.payment_provider import (
    CheckoutLinkResult,
    ProviderPaymentStatus,
    WebhookPayload,
)
from src.domain.enums import PaymentStatus
from src.domain.exceptions import InvalidWebhookSignatureException

_PAYOS_STATUS_MAP: dict[str, PaymentStatus] = {
    "PENDING": PaymentStatus.PENDING,
    "PROCESSING": PaymentStatus.PENDING,
    "UNDERPAID": PaymentStatus.PENDING,
    "PAID": PaymentStatus.PAID,
    "CANCELLED": PaymentStatus.CANCELLED,
    "EXPIRED": PaymentStatus.EXPIRED,
    "FAILED": PaymentStatus.FAILED,
}


class PayOsClientProtocol(Protocol):
    """The slice of ``payos.AsyncPayOS`` this adapter calls — narrowed to a
    Protocol so tests substitute a fake without touching the real SDK."""

    payment_requests: Any
    webhooks: Any


@dataclass
class PayOsPaymentProvider:
    client: PayOsClientProtocol
    checksum_key: str

    async def create_checkout_link(
        self, order_code: int, amount: Decimal, description: str, cancel_url: str, return_url: str
    ) -> CheckoutLinkResult:
        from payos.types import CreatePaymentLinkRequest

        response = await self.client.payment_requests.create(
            payment_data=CreatePaymentLinkRequest(
                order_code=order_code,
                amount=int(amount),
                description=description,
                cancel_url=cancel_url,
                return_url=return_url,
            )
        )
        return CheckoutLinkResult(
            payment_link_id=response.payment_link_id,
            checkout_url=response.checkout_url,
            qr_code=response.qr_code,
        )

    async def get_payment_status(self, order_code: int) -> ProviderPaymentStatus:
        response = await self.client.payment_requests.get(id=order_code)
        status = _PAYOS_STATUS_MAP.get(response.status, PaymentStatus.PENDING)
        return ProviderPaymentStatus(
            order_code=order_code, status=status, succeeded=status is PaymentStatus.PAID
        )

    async def cancel(self, order_code: int, reason: str | None) -> None:
        await self.client.payment_requests.cancel(id=order_code, cancellation_reason=reason)

    def verify_webhook(self, raw_body: bytes) -> WebhookPayload:
        try:
            data = self.client.webhooks.verify(raw_body)
        except payos.InvalidSignatureError as exc:
            raise InvalidWebhookSignatureException(str(exc)) from exc
        succeeded = data.code == "00"
        return WebhookPayload(
            order_code=data.order_code,
            status=PaymentStatus.PAID if succeeded else PaymentStatus.FAILED,
            succeeded=succeeded,
        )
