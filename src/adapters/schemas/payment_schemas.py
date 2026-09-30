"""HTTP wire models for the payment API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from src.adapters.schemas.base import CamelModel, MoneyField
from src.application.dtos.payment import CheckoutOutputDTO, PaymentOutputDTO
from src.domain.enums import PaymentStatus, PlanType


class CreateCheckoutRequest(CamelModel):
    # coin_redeem is not purchasable — it would be priced as an annual plan.
    plan_type: Literal[PlanType.MONTHLY, PlanType.ANNUAL]


class CheckoutResponse(CamelModel):
    order_code: int
    checkout_url: str
    qr_code: str
    amount: MoneyField
    plan_type: PlanType
    status: PaymentStatus

    @classmethod
    def from_dto(cls, dto: CheckoutOutputDTO) -> CheckoutResponse:
        return cls(
            order_code=dto.order_code,
            checkout_url=dto.checkout_url,
            qr_code=dto.qr_code,
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
