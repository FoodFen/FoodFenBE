"""HTTP wire models for the subscription API."""

from __future__ import annotations

from datetime import date

from src.adapters.schemas.base import CamelModel, MoneyField
from src.application.dtos.subscription import SubscriptionOutputDTO
from src.domain.enums import PlanType, SubscriptionStatus


class SubscriptionResponse(CamelModel):
    plan_type: PlanType
    status: SubscriptionStatus
    start_date: date
    end_date: date | None
    price: MoneyField

    @classmethod
    def from_dto(cls, dto: SubscriptionOutputDTO) -> SubscriptionResponse:
        return cls(
            plan_type=dto.plan_type,
            status=dto.status,
            start_date=dto.start_date,
            end_date=dto.end_date,
            price=dto.price,
        )


class MySubscriptionResponse(CamelModel):
    has_active_subscription: bool
    subscription: SubscriptionResponse | None

    @classmethod
    def from_dto(cls, dto: SubscriptionOutputDTO | None) -> MySubscriptionResponse:
        if dto is None:
            return cls(has_active_subscription=False, subscription=None)
        return cls(
            has_active_subscription=dto.status.value == "active",
            subscription=SubscriptionResponse.from_dto(dto),
        )
