"""Analyze a one-sentence meal description (typed or dictated): extract ingredients."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.ai_trial import AiCallerDTO
from src.application.dtos.food_analysis import FoodAnalysisDTO
from src.application.ports.food_vision_provider import FoodVisionProviderProtocol
from src.application.use_cases.ai_trial import AiTrialUseCase
from src.domain.enums import AiTrialMethod


@dataclass
class AnalyzeFoodTextUseCase:
    vision: FoodVisionProviderProtocol
    trial: AiTrialUseCase

    async def execute(
        self, caller: AiCallerDTO, method: AiTrialMethod, description: str, language: str
    ) -> FoodAnalysisDTO:
        await self.trial.ensure_available(caller, method)
        result = await self.vision.analyze_text(description, language)
        if result.ingredients:  # an empty analysis is a miss, not a spent trial
            await self.trial.consume(caller, method)
        return result
