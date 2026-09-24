"""Food entry / ingredient DTOs — frozen dataclasses, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient
from src.domain.enums import AiFeedback, InputMethod


@dataclass(frozen=True)
class CreateIngredientInputDTO:
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None = None


@dataclass(frozen=True)
class CreateFoodEntryInputDTO:
    user_id: int
    name: str
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    image_url: str | None = None
    fiber_g: float | None = None
    ingredients: list[CreateIngredientInputDTO] | None = None


@dataclass(frozen=True)
class IngredientOutputDTO:
    id: UUID
    name: str
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None

    @classmethod
    def from_entity(cls, ingredient: Ingredient) -> IngredientOutputDTO:
        return cls(
            id=ingredient.id,
            name=ingredient.name,
            quantity_g=ingredient.quantity_g,
            kcal=ingredient.kcal,
            carbs_g=ingredient.carbs_g,
            protein_g=ingredient.protein_g,
            fat_g=ingredient.fat_g,
            fiber_g=ingredient.fiber_g,
        )


@dataclass(frozen=True)
class FoodEntryOutputDTO:
    id: UUID
    name: str
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    image_url: str | None
    fiber_g: float | None
    ai_feedback: AiFeedback | None
    logged_at: datetime
    ingredients: list[IngredientOutputDTO]

    @classmethod
    def from_entity(cls, entry: FoodEntry) -> FoodEntryOutputDTO:
        return cls(
            id=entry.id,
            name=entry.name,
            input_method=entry.input_method,
            total_kcal=entry.total_kcal,
            carbs_g=entry.carbs_g,
            protein_g=entry.protein_g,
            fat_g=entry.fat_g,
            image_url=entry.image_url,
            fiber_g=entry.fiber_g,
            ai_feedback=entry.ai_feedback,
            logged_at=entry.logged_at,
            ingredients=[IngredientOutputDTO.from_entity(i) for i in entry.ingredients],
        )
