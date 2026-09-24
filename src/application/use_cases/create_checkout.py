"""Use case: start a PayOS checkout for a plan purchase."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.application.dtos.payment import CheckoutOutputDTO, CreateCheckoutInputDTO
from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.domain.entities.payment import Payment
from src.domain.enums import PlanType


@dataclass
class CreateCheckoutUseCase:
    payments: PaymentRepositoryProtocol
    provider: PaymentProviderProtocol
    monthly_price_vnd: int
    annual_price_vnd: int
    return_url: str
    cancel_url: str

    def _price_for(self, plan_type: PlanType) -> Decimal:
        vnd = self.monthly_price_vnd if plan_type is PlanType.MONTHLY else self.annual_price_vnd
        return Decimal(vnd)

    async def execute(self, input_dto: CreateCheckoutInputDTO) -> CheckoutOutputDTO:
        amount = self._price_for(input_dto.plan_type)
        payment = Payment.create(input_dto.user_id, input_dto.plan_type, amount)
        payment = await self.payments.create(payment)
        assert payment.order_code is not None  # DB identity column, assigned on insert

        link = await self.provider.create_checkout_link(
            order_code=payment.order_code,
            amount=amount,
            description=f"FoodFen {input_dto.plan_type.value} premium",
            cancel_url=self.cancel_url,
            return_url=self.return_url,
        )
        payment.attach_checkout(link.payment_link_id, link.checkout_url, link.qr_code)
        payment = await self.payments.update(payment)
        return CheckoutOutputDTO.from_entity(payment)
