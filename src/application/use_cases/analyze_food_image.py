"""Analyze a meal photo: extract ingredients, persist the image."""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.application.dtos.ai_trial import AiCallerDTO
from src.application.dtos.food_analysis import FoodAnalysisDTO
from src.application.ports.food_vision_provider import FoodVisionProviderProtocol
from src.application.ports.image_storage import ImageStorageProtocol
from src.application.use_cases.ai_trial import AiTrialUseCase
from src.domain.enums import AiTrialMethod


@dataclass
class AnalyzeFoodImageUseCase:
    vision: FoodVisionProviderProtocol
    images: ImageStorageProtocol
    trial: AiTrialUseCase

    async def execute(
        self, caller: AiCallerDTO, image_bytes: bytes, content_type: str, language: str
    ) -> FoodAnalysisDTO:
        await self.trial.ensure_available(caller, AiTrialMethod.IMAGE)
        result = await self.vision.analyze_image(image_bytes, content_type, language)
        image_url = await self.images.upload(image_bytes, content_type)
        if result.ingredients:  # an empty analysis is a miss, not a spent trial
            await self.trial.consume(caller, AiTrialMethod.IMAGE)
        return replace(result, image_url=image_url)
