"""Analyze a one-sentence meal description: extract ingredients."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.food_analysis import FoodAnalysisDTO
from src.application.ports.food_vision_provider import FoodVisionProviderProtocol


@dataclass
class AnalyzeFoodTextUseCase:
    vision: FoodVisionProviderProtocol

    async def execute(self, description: str, language: str) -> FoodAnalysisDTO:
        return await self.vision.analyze_text(description, language)
