"""Use case: read a payment's status, reconciling with the provider if still pending.

The reconciliation step is the fallback for a lost or delayed webhook.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.payment import PaymentOutputDTO
from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.application.use_cases.apply_payment_result import apply_payment_result
from src.domain.enums import PaymentProvider, PaymentStatus
from src.domain.exceptions import PaymentNotFoundException


@dataclass
class GetPaymentStatusUseCase:
    payments: PaymentRepositoryProtocol
    providers: dict[PaymentProvider, PaymentProviderProtocol]
    subscriptions: SubscriptionRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(self, user_id: int, order_code: int) -> PaymentOutputDTO:
        payment = await self.payments.get_by_order_code(order_code)
        if payment is None or payment.user_id != user_id:
            raise PaymentNotFoundException(f"no payment for order_code {order_code}")

        provider = self.providers.get(payment.provider)
        if payment.status is PaymentStatus.PENDING and provider is not None:
            provider_status = await provider.get_payment_status(order_code)
            if provider_status.status is not PaymentStatus.PENDING:
                payment = await apply_payment_result(
                    payment, provider_status.succeeded, self.payments, self.subscriptions, self.users
                )

        return PaymentOutputDTO.from_entity(payment)
