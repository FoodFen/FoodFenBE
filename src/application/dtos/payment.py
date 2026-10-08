"""Payment DTOs — frozen dataclasses, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from src.domain.entities.payment import Payment
from src.domain.enums import PaymentProvider, PaymentStatus, PlanType


@dataclass(frozen=True)
class CreateCheckoutInputDTO:
    user_id: int
    plan_type: PlanType
    provider: PaymentProvider = PaymentProvider.PAYOS


@dataclass(frozen=True)
class CheckoutOutputDTO:
    order_code: int
    provider: PaymentProvider
    checkout_url: str
    qr_code: str | None
    deeplink: str | None
    amount: Decimal
    plan_type: PlanType
    status: PaymentStatus

    @classmethod
    def from_entity(cls, payment: Payment, deeplink: str | None) -> CheckoutOutputDTO:
        assert payment.order_code is not None
        assert payment.checkout_url is not None
        return cls(
            order_code=payment.order_code,
            provider=payment.provider,
            checkout_url=payment.checkout_url,
            qr_code=payment.qr_code,
            deeplink=deeplink,
            amount=payment.amount,
            plan_type=payment.plan_type,
            status=payment.status,
        )


@dataclass(frozen=True)
class PaymentOutputDTO:
    order_code: int
    status: PaymentStatus
    amount: Decimal
    plan_type: PlanType
    paid_at: datetime | None
    created_at: datetime

    @classmethod
    def from_entity(cls, payment: Payment) -> PaymentOutputDTO:
        assert payment.order_code is not None
        return cls(
            order_code=payment.order_code,
            status=payment.status,
            amount=payment.amount,
            plan_type=payment.plan_type,
            paid_at=payment.paid_at,
            created_at=payment.created_at,
        )


@dataclass(frozen=True)
class PlanOutputDTO:
    plan_type: PlanType
    price_vnd: int


@dataclass(frozen=True)
class PlansOutputDTO:
    plans: list[PlanOutputDTO]
    providers: list[PaymentProvider]
