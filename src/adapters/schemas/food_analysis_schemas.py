"""HTTP wire models for the AI food capture API contract."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Literal

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.application.dtos.food_analysis import FoodAnalysisDTO, IngredientSuggestionDTO
from src.domain.enums import AiTrialMethod


class Per100gResponse(CamelModel):
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None


class IngredientSuggestionResponse(CamelModel):
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None
    confidence: float
    # Set only when the row is grounded in the food catalog (see application/food_grounding.py).
    catalog_food_id: str | None
    catalog_name: str | None
    verified: bool
    source_ref: str | None
    # to_camel would give "per100G"; the contract says "per100g".
    per100g: Per100gResponse | None = Field(alias="per100g")

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
            catalog_food_id=dto.catalog_food_id,
            catalog_name=dto.catalog_name,
            verified=dto.verified,
            source_ref=dto.source_ref,
            per100g=Per100gResponse(**asdict(dto.per100g)) if dto.per100g else None,
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
    description: str = Field(min_length=1, max_length=1000)
    language: Literal["vi", "en"] = "vi"
    # Voice is dictated text sent to this same endpoint; only the free-trial counter cares.
    input_method: Literal["text", "voice"] = "text"


class QuotaCounterResponse(CamelModel):
    limit: int
    remaining: int


class AiQuotaResponse(CamelModel):
    """Free trials left today per input method. ``unlimited`` (Premium) leaves the counters and
    ``resets_at`` null."""

    unlimited: bool
    resets_at: datetime | None
    image: QuotaCounterResponse | None
    text: QuotaCounterResponse | None
    voice: QuotaCounterResponse | None

    @classmethod
    def from_remaining(
        cls, remaining: dict[AiTrialMethod, int] | None, limit: int, resets_at: datetime
    ) -> AiQuotaResponse:
        if remaining is None:
            return cls(unlimited=True, resets_at=None, image=None, text=None, voice=None)

        def counter(method: AiTrialMethod) -> QuotaCounterResponse:
            return QuotaCounterResponse(limit=limit, remaining=remaining[method])

        return cls(
            unlimited=False,
            resets_at=resets_at,
            image=counter(AiTrialMethod.IMAGE),
            text=counter(AiTrialMethod.TEXT),
            voice=counter(AiTrialMethod.VOICE),
        )
