"""HTTP wire models for the payment API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from src.adapters.schemas.base import CamelModel, MoneyField
from src.application.dtos.payment import CheckoutOutputDTO, PaymentOutputDTO, PlansOutputDTO
from src.domain.enums import PaymentProvider, PaymentStatus, PlanType


class CreateCheckoutRequest(CamelModel):
    # coin_redeem is not purchasable — it would be priced as an annual plan.
    plan_type: Literal[PlanType.MONTHLY, PlanType.ANNUAL]
    provider: PaymentProvider = PaymentProvider.PAYOS


class CheckoutResponse(CamelModel):
    order_code: int
    provider: PaymentProvider
    checkout_url: str
    qr_code: str | None
    deeplink: str | None
    amount: MoneyField
    plan_type: PlanType
    status: PaymentStatus

    @classmethod
    def from_dto(cls, dto: CheckoutOutputDTO) -> CheckoutResponse:
        return cls(
            order_code=dto.order_code,
            provider=dto.provider,
            checkout_url=dto.checkout_url,
            qr_code=dto.qr_code,
            deeplink=dto.deeplink,
            amount=dto.amount,
            plan_type=dto.plan_type,
            status=dto.status,
        )


class PaymentResponse(CamelModel):
    order_code: int
    status: PaymentStatus
    amount: MoneyField
    plan_type: PlanType
    paid_at: datetime | None
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: PaymentOutputDTO) -> PaymentResponse:
        return cls(
            order_code=dto.order_code,
            status=dto.status,
            amount=dto.amount,
            plan_type=dto.plan_type,
            paid_at=dto.paid_at,
            created_at=dto.created_at,
        )


class CancelPaymentRequest(CamelModel):
    cancellation_reason: str | None = None


class PlanResponse(CamelModel):
    plan_type: PlanType
    price_vnd: int


class PlansResponse(CamelModel):
    plans: list[PlanResponse]
    providers: list[PaymentProvider]

    @classmethod
    def from_dto(cls, dto: PlansOutputDTO) -> PlansResponse:
        return cls(plans=[PlanResponse(**vars(d)) for d in dto.plans], providers=dto.providers)
