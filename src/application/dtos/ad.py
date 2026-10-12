"""Paid-placement DTOs: frozen dataclasses, never Pydantic or ORM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from src.domain.entities.ad_package import AdPackage


@dataclass(frozen=True)
class AdPackageDTO:
    id: UUID
    days: int
    price_vnd: Decimal
    active: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, p: AdPackage) -> AdPackageDTO:
        return cls(id=p.id, days=p.days, price_vnd=p.price_vnd, active=p.active, created_at=p.created_at)


@dataclass(frozen=True)
class AdImpressionDayDTO:
    date: date
    count: int


@dataclass(frozen=True)
class MyAdsDTO:
    featured_until: datetime | None
    packages: list[AdPackageDTO]  # active only, fewest days first
    impressions: list[AdImpressionDayDTO]  # last 30 Vietnam days, oldest first, zero-filled
