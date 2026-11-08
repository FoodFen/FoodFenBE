"""Use cases: list / create / edit / delete nutrition tips. Text rules live in the ``NutritionTip`` entity."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.ports.nutrition_tip_repository import NutritionTipRepositoryProtocol
from src.domain.entities.nutrition_tip import NutritionTip
from src.domain.exceptions import NutritionTipNotFoundException


@dataclass
class ListNutritionTipsUseCase:
    tips: NutritionTipRepositoryProtocol

    async def execute(self, active_only: bool) -> list[NutritionTip]:
        return await self.tips.list(active_only)


@dataclass
class CreateNutritionTipUseCase:
    tips: NutritionTipRepositoryProtocol

    async def execute(self, text_vi: str, text_en: str, is_active: bool) -> NutritionTip:
        tip = NutritionTip.create(text_vi, text_en, is_active)
        await self.tips.add(tip)
        return tip


@dataclass
class UpdateNutritionTipUseCase:
    tips: NutritionTipRepositoryProtocol

    async def execute(
        self, tip_id: UUID, text_vi: str | None, text_en: str | None, is_active: bool | None
    ) -> NutritionTip:
        tip = await self.tips.get(tip_id)
        if tip is None:
            raise NutritionTipNotFoundException(f"no nutrition tip {tip_id}")
        tip.update(text_vi, text_en, is_active)
        await self.tips.update(tip)
        return tip


@dataclass
class DeleteNutritionTipUseCase:
    tips: NutritionTipRepositoryProtocol

    async def execute(self, tip_id: UUID) -> None:
        if await self.tips.get(tip_id) is None:
            raise NutritionTipNotFoundException(f"no nutrition tip {tip_id}")
        await self.tips.delete(tip_id)
