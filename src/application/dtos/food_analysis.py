"""DTOs for AI food capture (image/text -> suggested ingredients). Standard library only."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NutritionPer100gDTO:
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None


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
    # From the provider, catalog_food_id is the model's unvalidated claim; after grounding it is a
    # known catalog slug or None (and the rest below is None/False for an ungrounded row).
    catalog_food_id: str | None = None
    catalog_name: str | None = None
    verified: bool = False
    source_ref: str | None = None
    per100g: NutritionPer100gDTO | None = None


@dataclass(frozen=True)
class FoodAnalysisDTO:
    meal_name: str
    ingredients: list[IngredientSuggestionDTO]
    # Set only when the image was persisted somewhere durable.
    image_url: str | None
