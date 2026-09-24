"""Use case: apply an incoming PayOS webhook (IPN) call."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.application.use_cases.apply_payment_result import apply_payment_result
from src.domain.exceptions import PaymentNotFoundException


@dataclass
class HandlePaymentWebhookUseCase:
    payments: PaymentRepositoryProtocol
    provider: PaymentProviderProtocol
    subscriptions: SubscriptionRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(self, raw_body: bytes) -> None:
        webhook = self.provider.verify_webhook(raw_body)  # raises InvalidWebhookSignatureException
        payment = await self.payments.get_by_order_code(webhook.order_code)
        if payment is None:
            raise PaymentNotFoundException(f"no payment for order_code {webhook.order_code}")
        await apply_payment_result(
            payment, webhook.succeeded, self.payments, self.subscriptions, self.users
        )
