"""Use case: cancel a pending checkout."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.payment import PaymentOutputDTO
from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.domain.enums import PaymentProvider, PaymentStatus
from src.domain.exceptions import InvalidPaymentStateException, PaymentNotFoundException


@dataclass
class CancelPaymentUseCase:
    payments: PaymentRepositoryProtocol
    providers: dict[PaymentProvider, PaymentProviderProtocol]

    async def execute(self, user_id: int, order_code: int, reason: str | None) -> PaymentOutputDTO:
        payment = await self.payments.get_by_order_code(order_code)
        if payment is None or payment.user_id != user_id:
            raise PaymentNotFoundException(f"no payment for order_code {order_code}")
        if payment.status is not PaymentStatus.PENDING:
            raise InvalidPaymentStateException(f"cannot cancel a payment in status {payment.status}")

        provider = self.providers.get(payment.provider)
        if provider is not None:
            await provider.cancel(order_code, reason)
        payment.mark_cancelled()
        payment = await self.payments.update(payment)
        return PaymentOutputDTO.from_entity(payment)
