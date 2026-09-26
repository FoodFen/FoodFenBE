"""DTOs for AI food capture (image/text -> suggested ingredients). Standard library only."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IngredientSuggestionDTO:
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    # None: the model had no basis to estimate it. Never 0 for "unknown".
    fiber_g: float | None
    # 0-1, UI-only — not persisted, so calibration only needs low=uncertain.
    confidence: float


@dataclass(frozen=True)
class FoodAnalysisDTO:
    meal_name: str
    ingredients: list[IngredientSuggestionDTO]
    # Set only when the image was persisted somewhere durable.
    image_url: str | None
