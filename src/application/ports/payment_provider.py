"""Port for a payment provider (PayOS, MoMo). Structural typing via Protocol."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from src.domain.enums import PaymentStatus


@dataclass(frozen=True)
class CheckoutLinkResult:
    payment_link_id: str
    checkout_url: str
    qr_code: str | None
    deeplink: str | None = None


@dataclass(frozen=True)
class ProviderPaymentStatus:
    order_code: int
    status: PaymentStatus
    succeeded: bool


@dataclass(frozen=True)
class WebhookPayload:
    order_code: int
    succeeded: bool


class PaymentProviderProtocol(Protocol):
    async def create_checkout_link(
        self,
        order_code: int,
        amount: Decimal,
        description: str,
        cancel_url: str,
        return_url: str,
    ) -> CheckoutLinkResult: ...

    async def get_payment_status(self, order_code: int) -> ProviderPaymentStatus: ...

    async def cancel(self, order_code: int, reason: str | None) -> None: ...

    def verify_webhook(self, raw_body: bytes) -> WebhookPayload:
        """Raise ``InvalidWebhookSignatureException`` if the signature doesn't match."""
        ...
