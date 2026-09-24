"""Subscription DTO — frozen dataclass, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.domain.entities.subscription import Subscription
from src.domain.enums import PlanType, SubscriptionStatus


@dataclass(frozen=True)
class SubscriptionOutputDTO:
    plan_type: PlanType
    status: SubscriptionStatus
    start_date: date
    end_date: date | None

    @classmethod
    def from_entity(cls, subscription: Subscription) -> SubscriptionOutputDTO:
        return cls(
            plan_type=subscription.plan_type,
            status=subscription.status,
            start_date=subscription.start_date,
            end_date=subscription.end_date,
        )
