"""HTTP wire models for the food entry (meal log) API."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.application.dtos.food_entry import FoodEntryOutputDTO, IngredientOutputDTO
from src.domain.enums import AiFeedback, InputMethod, MealType


class CreateIngredientRequest(CamelModel):
    name: str = Field(min_length=1)
    quantity_g: float
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None = None


class CreateFoodEntryRequest(CamelModel):
    name: str = Field(min_length=1)
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    meal_type: MealType
    client_id: str = Field(min_length=1)
    image_url: str | None = None
    fiber_g: float | None = None
    ingredients: list[CreateIngredientRequest] = Field(default_factory=list)
    logged_at: datetime | None = None
    logged_on: date | None = None


class IngredientResponse(CamelModel):
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
    def from_dto(cls, dto: IngredientOutputDTO) -> IngredientResponse:
        return cls(
            id=dto.id,
            food_entry_id=dto.food_entry_id,
            name=dto.name,
            quantity_g=dto.quantity_g,
            kcal=dto.kcal,
            carbs_g=dto.carbs_g,
            protein_g=dto.protein_g,
            fat_g=dto.fat_g,
            fiber_g=dto.fiber_g,
        )


class FoodEntryResponse(CamelModel):
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
    ingredients: list[IngredientResponse]

    @classmethod
    def from_dto(cls, dto: FoodEntryOutputDTO) -> FoodEntryResponse:
        return cls(
            id=dto.id,
            user_id=dto.user_id,
            name=dto.name,
            input_method=dto.input_method,
            meal_type=dto.meal_type,
            total_kcal=dto.total_kcal,
            carbs_g=dto.carbs_g,
            protein_g=dto.protein_g,
            fat_g=dto.fat_g,
            image_url=dto.image_url,
            fiber_g=dto.fiber_g,
            ai_feedback=dto.ai_feedback,
            logged_at=dto.logged_at,
            logged_on=dto.logged_on,
            ingredients=[IngredientResponse.from_dto(i) for i in dto.ingredients],
        )


class UpdateFoodEntryRequest(CamelModel):
    name: str = Field(min_length=1)
    input_method: InputMethod
    total_kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    meal_type: MealType
    image_url: str | None = None
    fiber_g: float | None = None
    ingredients: list[CreateIngredientRequest] = Field(default_factory=list)
    logged_at: datetime | None = None
    logged_on: date | None = None
