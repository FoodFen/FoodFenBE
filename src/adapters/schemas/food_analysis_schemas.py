"""HTTP wire models for the AI food capture API contract."""

from __future__ import annotations

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.application.dtos.food_analysis import FoodAnalysisDTO, IngredientSuggestionDTO


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
