"""HTTP wire models for paid placement (camelCase). ``priceVnd`` and ``days`` are JSON integers."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.application.dtos.ad import AdPackageDTO, MyAdsDTO
from src.domain.enums import PaymentProvider


class OwnerAdPackageResponse(CamelModel):
    id: UUID
    days: int
    price_vnd: int  # Decimal in the domain; whole VND on the wire, like PlanResponse

    @classmethod
    def from_dto(cls, dto: AdPackageDTO) -> OwnerAdPackageResponse:
        return cls(id=dto.id, days=dto.days, price_vnd=int(dto.price_vnd))


class AdPackageResponse(OwnerAdPackageResponse):
    active: bool
    created_at: datetime

    @classmethod
    def from_dto(cls, dto: AdPackageDTO) -> AdPackageResponse:
        return cls(
            id=dto.id, days=dto.days, price_vnd=int(dto.price_vnd), active=dto.active, created_at=dto.created_at
        )


class AdImpressionResponse(CamelModel):
    date: date
    count: int


class MyAdsResponse(CamelModel):
    featured_until: datetime | None
    packages: list[OwnerAdPackageResponse]
    impressions: list[AdImpressionResponse]

    @classmethod
    def from_dto(cls, dto: MyAdsDTO) -> MyAdsResponse:
        return cls(
            featured_until=dto.featured_until,
            packages=[OwnerAdPackageResponse.from_dto(p) for p in dto.packages],
            impressions=[AdImpressionResponse(**vars(i)) for i in dto.impressions],
        )


class CreateAdCheckoutRequest(CamelModel):
    package_id: UUID
    provider: PaymentProvider = PaymentProvider.PAYOS


class CreateAdPackageRequest(CamelModel):
    days: int = Field(gt=0, le=3650)
    price_vnd: int = Field(gt=0, le=999_999_999_999)  # fits Numeric(12, 0)
    active: bool = True


class UpdateAdPackageRequest(CamelModel):
    """Partial: an absent (or null) field is left as is."""

    days: int | None = Field(default=None, gt=0, le=3650)
    price_vnd: int | None = Field(default=None, gt=0, le=999_999_999_999)
    active: bool | None = None
