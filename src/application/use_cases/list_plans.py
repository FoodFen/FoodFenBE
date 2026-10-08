"""Use case: the purchasable Premium plans and their prices (the same ones checkout charges)."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.payment import PlanOutputDTO, PlansOutputDTO
from src.domain.enums import PaymentProvider, PlanType


@dataclass
class ListPlansUseCase:
    monthly_price_vnd: int
    annual_price_vnd: int
    providers: list[PaymentProvider]

    def execute(self) -> PlansOutputDTO:
        return PlansOutputDTO(
            plans=[
                PlanOutputDTO(PlanType.MONTHLY, self.monthly_price_vnd),
                PlanOutputDTO(PlanType.ANNUAL, self.annual_price_vnd),
            ],
            providers=self.providers,
        )
