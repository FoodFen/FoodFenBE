"""Food entry (meal log) endpoints. HTTP <-> application DTO translation only."""

from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from src.adapters.schemas.food_entry_schemas import CreateFoodEntryRequest, FoodEntryResponse
from src.application.dtos.food_entry import CreateFoodEntryInputDTO, CreateIngredientInputDTO
from src.infrastructure.di import (
    CreateFoodEntryUseCaseDep,
    CurrentUserDep,
    GetFoodEntryUseCaseDep,
    ListFoodEntriesUseCaseDep,
)

router = APIRouter(prefix="/food-entries", tags=["food-entries"])


@router.post("", response_model=FoodEntryResponse)
async def create_food_entry(
    body: CreateFoodEntryRequest,
    user: CurrentUserDep,
    use_case: CreateFoodEntryUseCaseDep,
) -> FoodEntryResponse:
    input_dto = CreateFoodEntryInputDTO(
        user_id=user.id,
        name=body.name,
        input_method=body.input_method,
        total_kcal=body.total_kcal,
        carbs_g=body.carbs_g,
        protein_g=body.protein_g,
        fat_g=body.fat_g,
        meal_type=body.meal_type,
        client_id=body.client_id,
        image_url=body.image_url,
        fiber_g=body.fiber_g,
        logged_on=body.logged_on,
        ingredients=[
            CreateIngredientInputDTO(
                name=i.name,
                quantity_g=i.quantity_g,
                kcal=i.kcal,
                carbs_g=i.carbs_g,
                protein_g=i.protein_g,
                fat_g=i.fat_g,
                fiber_g=i.fiber_g,
            )
            for i in body.ingredients
        ],
    )
    result = await use_case.execute(input_dto)
    return FoodEntryResponse.from_dto(result)


@router.get("", response_model=list[FoodEntryResponse])
async def list_food_entries(
    user: CurrentUserDep,
    use_case: ListFoodEntriesUseCaseDep,
    from_: Annotated[date, Query(alias="from")],
    to: Annotated[date, Query()],
) -> list[FoodEntryResponse]:
    result = await use_case.execute(user.id, from_, to)
    return [FoodEntryResponse.from_dto(dto) for dto in result]


@router.get("/{entry_id}", response_model=FoodEntryResponse)
async def get_food_entry(
    entry_id: UUID, user: CurrentUserDep, use_case: GetFoodEntryUseCaseDep
) -> FoodEntryResponse:
    result = await use_case.execute(user_id=user.id, entry_id=entry_id)
    return FoodEntryResponse.from_dto(result)
