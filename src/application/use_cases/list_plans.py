"""Use case: the purchasable Premium plans and their prices (the same ones checkout charges)."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.payment import PlanOutputDTO
from src.domain.enums import PlanType


@dataclass
class ListPlansUseCase:
    monthly_price_vnd: int
    annual_price_vnd: int

    def execute(self) -> list[PlanOutputDTO]:
        return [
            PlanOutputDTO(PlanType.MONTHLY, self.monthly_price_vnd),
            PlanOutputDTO(PlanType.ANNUAL, self.annual_price_vnd),
        ]
