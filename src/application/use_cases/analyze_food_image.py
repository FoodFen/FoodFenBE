"""Analyze a meal photo: extract ingredients, persist the image."""

from __future__ import annotations

from dataclasses import dataclass, replace

from src.application.dtos.food_analysis import FoodAnalysisDTO
from src.application.ports.food_vision_provider import FoodVisionProviderProtocol
from src.application.ports.image_storage import ImageStorageProtocol


@dataclass
class AnalyzeFoodImageUseCase:
    vision: FoodVisionProviderProtocol
    images: ImageStorageProtocol

    async def execute(self, image_bytes: bytes, content_type: str) -> FoodAnalysisDTO:
        result = await self.vision.analyze_image(image_bytes, content_type)
        image_url = await self.images.upload(image_bytes, content_type)
        return replace(result, image_url=image_url)
