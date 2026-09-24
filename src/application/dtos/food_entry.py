"""Food entry / ingredient DTOs — frozen dataclasses, never a Pydantic model or ORM row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient
from src.domain.enums import AiFeedback, InputMethod, MealType


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
    meal_type: MealType
    client_id: str
    image_url: str | None = None
    fiber_g: float | None = None
    ingredients: list[CreateIngredientInputDTO] | None = None
    logged_on: date | None = None


@dataclass(frozen=True)
class IngredientOutputDTO:
    id: UUID
    food_entry_id: UUID
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
            food_entry_id=ingredient.food_entry_id,
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
    user_id: int
    name: str
    input_method: InputMethod
    meal_type: MealType
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    image_url: str | None
    fiber_g: float | None
    ai_feedback: AiFeedback | None
    logged_at: datetime
    logged_on: date
    ingredients: list[IngredientOutputDTO]

    @classmethod
    def from_entity(cls, entry: FoodEntry) -> FoodEntryOutputDTO:
        return cls(
            id=entry.id,
            user_id=entry.user_id,
            name=entry.name,
            input_method=entry.input_method,
            meal_type=entry.meal_type,
            total_kcal=entry.total_kcal,
            carbs_g=entry.carbs_g,
            protein_g=entry.protein_g,
            fat_g=entry.fat_g,
            image_url=entry.image_url,
            fiber_g=entry.fiber_g,
            ai_feedback=entry.ai_feedback,
            logged_at=entry.logged_at,
            logged_on=entry.logged_on,
            ingredients=[IngredientOutputDTO.from_entity(i) for i in entry.ingredients],
        )
