"""Analyze a meal photo: extract ingredients, persist the image."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace

from src.application.dtos.ai_trial import AiCallerDTO
from src.application.dtos.food_analysis import FoodAnalysisDTO
from src.application.food_catalog_cache import FoodCatalogCache
from src.application.food_grounding import ground, record_misses
from src.application.ports.food_catalog_repository import FoodCatalogRepositoryProtocol
from src.application.ports.food_miss_repository import FoodMissRepositoryProtocol
from src.application.ports.food_vision_provider import FoodVisionProviderProtocol
from src.application.ports.image_storage import ImageStorageProtocol
from src.application.use_cases.ai_trial import AiTrialUseCase
from src.domain.enums import AiTrialMethod

_log = logging.getLogger("foodfenbe.food_analysis")


@dataclass
class AnalyzeFoodImageUseCase:
    vision: FoodVisionProviderProtocol
    images: ImageStorageProtocol
    trial: AiTrialUseCase
    catalog: FoodCatalogRepositoryProtocol
    catalog_cache: FoodCatalogCache
    misses: FoodMissRepositoryProtocol
    grounding: bool

    async def execute(
        self, caller: AiCallerDTO, image_bytes: bytes, content_type: str, language: str
    ) -> FoodAnalysisDTO:
        await self.trial.ensure_available(caller, AiTrialMethod.IMAGE)
        foods = await self.catalog_cache.get(self.catalog) if self.grounding else {}
        result, image_url = await asyncio.gather(
            self.vision.analyze_image(
                image_bytes, content_type, language, catalog=list(foods.values()) or None
            ),
            self._upload_or_none(image_bytes, content_type),
        )
        if foods:
            result = ground(result, foods)
            await record_misses(self.misses, result, language)
        if result.ingredients:  # an empty analysis is a miss, not a spent trial
            await self.trial.consume(caller, AiTrialMethod.IMAGE)
        return replace(result, image_url=image_url)

    async def _upload_or_none(self, image_bytes: bytes, content_type: str) -> str | None:
        try:
            return await self.images.upload(image_bytes, content_type)
        except Exception:  # the analysis is the product; a missing thumbnail isn't worth failing it
            _log.warning("meal image upload failed", exc_info=True)
            return None
