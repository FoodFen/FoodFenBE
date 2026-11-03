"""Analyze a one-sentence meal description (typed or dictated): extract ingredients."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.ai_trial import AiCallerDTO
from src.application.dtos.food_analysis import FoodAnalysisDTO
from src.application.food_catalog_cache import FoodCatalogCache
from src.application.food_grounding import ground, record_misses
from src.application.ports.food_catalog_repository import FoodCatalogRepositoryProtocol
from src.application.ports.food_miss_repository import FoodMissRepositoryProtocol
from src.application.ports.food_vision_provider import FoodVisionProviderProtocol
from src.application.use_cases.ai_trial import AiTrialUseCase
from src.domain.enums import AiTrialMethod


@dataclass
class AnalyzeFoodTextUseCase:
    vision: FoodVisionProviderProtocol
    trial: AiTrialUseCase
    catalog: FoodCatalogRepositoryProtocol
    catalog_cache: FoodCatalogCache
    misses: FoodMissRepositoryProtocol
    grounding: bool

    async def execute(
        self, caller: AiCallerDTO, method: AiTrialMethod, description: str, language: str
    ) -> FoodAnalysisDTO:
        await self.trial.ensure_available(caller, method)
        foods = await self.catalog_cache.get(self.catalog) if self.grounding else {}
        result = await self.vision.analyze_text(
            description, language, catalog=list(foods.values()) or None
        )
        if foods:
            result = ground(result, foods)
            await record_misses(self.misses, result, language)
        if result.ingredients:  # an empty analysis is a miss, not a spent trial
            await self.trial.consume(caller, method)
        return result
