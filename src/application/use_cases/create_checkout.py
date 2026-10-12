"""Use case: start a checkout for a plan purchase."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.application.dtos.payment import CheckoutOutputDTO, CreateCheckoutInputDTO
from src.application.ports.payment_provider import PaymentProviderProtocol
from src.application.ports.payment_repository import PaymentRepositoryProtocol
from src.domain.entities.payment import Payment
from src.domain.enums import PaymentProvider, PlanType
from src.domain.exceptions import PaymentProviderUnavailableException


async def start_checkout(
    payments: PaymentRepositoryProtocol,
    provider: PaymentProviderProtocol,
    payment: Payment,
    description: str,
    cancel_url: str,
    return_url: str,
) -> CheckoutOutputDTO:
    """Persist a new payment and open its provider checkout link. Shared by Premium and ad checkouts."""
    payment = await payments.create(payment)
    assert payment.order_code is not None  # DB identity column, assigned on insert

    link = await provider.create_checkout_link(
        order_code=payment.order_code,
        amount=payment.amount,
        description=description,
        cancel_url=cancel_url,
        return_url=return_url,
    )
    payment.attach_checkout(link.payment_link_id, link.checkout_url, link.qr_code)
    payment = await payments.update(payment)
    return CheckoutOutputDTO.from_entity(payment, link.deeplink)


@dataclass
class CreateCheckoutUseCase:
    payments: PaymentRepositoryProtocol
    providers: dict[PaymentProvider, PaymentProviderProtocol]
    monthly_price_vnd: int
    annual_price_vnd: int
    return_url: str
    cancel_url: str

    def _price_for(self, plan_type: PlanType) -> Decimal:
        vnd = self.monthly_price_vnd if plan_type is PlanType.MONTHLY else self.annual_price_vnd
        return Decimal(vnd)

    async def execute(self, input_dto: CreateCheckoutInputDTO) -> CheckoutOutputDTO:
        provider = self.providers.get(input_dto.provider)
        if provider is None:
            raise PaymentProviderUnavailableException(
                f"payment provider {input_dto.provider} is not enabled"
            )
        payment = Payment.create(
            input_dto.user_id, input_dto.plan_type, self._price_for(input_dto.plan_type), input_dto.provider
        )
        # MoMo keeps its own app deep link (momo_redirect_url): it gets no return URL, PayOS does.
        payos = input_dto.provider is PaymentProvider.PAYOS
        return await start_checkout(
            self.payments, provider, payment, f"FoodFen {input_dto.plan_type.value} premium",
            self.cancel_url if payos else "", self.return_url if payos else "",
        )
