"""HTTP wire models for the AI food capture API contract."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.application.dtos.food_analysis import FoodAnalysisDTO, IngredientSuggestionDTO
from src.application.use_cases.ai_trial import AI_TRIAL_LIMIT
from src.domain.enums import AiTrialMethod


class IngredientSuggestionResponse(CamelModel):
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None
    confidence: float

    @classmethod
    def from_dto(cls, dto: IngredientSuggestionDTO) -> IngredientSuggestionResponse:
        return cls(
            name=dto.name,
            quantity_g=dto.quantity_g,
            kcal=dto.kcal,
            carbs_g=dto.carbs_g,
            protein_g=dto.protein_g,
            fat_g=dto.fat_g,
            fiber_g=dto.fiber_g,
            confidence=dto.confidence,
        )


class FoodAnalysisResponse(CamelModel):
    meal_name: str
    ingredients: list[IngredientSuggestionResponse]
    image_url: str | None

    @classmethod
    def from_dto(cls, dto: FoodAnalysisDTO) -> FoodAnalysisResponse:
        return cls(
            meal_name=dto.meal_name,
            ingredients=[IngredientSuggestionResponse.from_dto(i) for i in dto.ingredients],
            image_url=dto.image_url,
        )


class AnalyzeFoodTextRequest(CamelModel):
    description: str = Field(min_length=1)
    language: Literal["vi", "en"] = "vi"
    # Voice is dictated text sent to this same endpoint; only the free-trial counter cares.
    input_method: Literal["text", "voice"] = "text"


class QuotaCounterResponse(CamelModel):
    limit: int
    remaining: int


class AiQuotaResponse(CamelModel):
    """Free trials left per input method. ``unlimited`` (Premium) leaves the counters null."""

    unlimited: bool
    image: QuotaCounterResponse | None
    text: QuotaCounterResponse | None
    voice: QuotaCounterResponse | None

    @classmethod
    def from_remaining(cls, remaining: dict[AiTrialMethod, int] | None) -> AiQuotaResponse:
        if remaining is None:
            return cls(unlimited=True, image=None, text=None, voice=None)

        def counter(method: AiTrialMethod) -> QuotaCounterResponse:
            return QuotaCounterResponse(limit=AI_TRIAL_LIMIT, remaining=remaining[method])

        return cls(
            unlimited=False,
            image=counter(AiTrialMethod.IMAGE),
            text=counter(AiTrialMethod.TEXT),
            voice=counter(AiTrialMethod.VOICE),
        )
