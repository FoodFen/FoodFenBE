"""CreateFoodEntryUseCase / GetFoodEntryUseCase unit tests. No I/O."""

from __future__ import annotations

import pytest

from src.application.dtos.food_entry import CreateFoodEntryInputDTO, CreateIngredientInputDTO
from src.application.use_cases.create_food_entry import CreateFoodEntryUseCase
from src.application.use_cases.get_food_entry import GetFoodEntryUseCase
from src.domain.entities.food_entry import FoodEntry
from src.domain.enums import InputMethod
from src.domain.exceptions import FoodEntryNotFoundException


class FakeFoodEntryRepo:
    def __init__(self) -> None:
        self._by_id: dict = {}

    async def create(self, entry: FoodEntry) -> FoodEntry:
        self._by_id[entry.id] = entry
        return entry

    async def get_by_id(self, entry_id):
        return self._by_id.get(entry_id)


def _input_dto(fiber_g=None, ingredient_fiber_g=None) -> CreateFoodEntryInputDTO:
    return CreateFoodEntryInputDTO(
        user_id=1,
        name="Grilled chicken with rice",
        input_method=InputMethod.MANUAL,
        total_kcal=650,
        carbs_g=70.0,
        protein_g=45.0,
        fat_g=15.0,
        image_url=None,
        fiber_g=fiber_g,
        ingredients=[
            CreateIngredientInputDTO(
                name="chicken breast",
                quantity_g=200.0,
                kcal=330,
                carbs_g=0.0,
                protein_g=40.0,
                fat_g=15.0,
                fiber_g=ingredient_fiber_g,
            )
        ],
    )


async def test_premium_user_keeps_fiber_g():
    use_case = CreateFoodEntryUseCase(food_entries=FakeFoodEntryRepo())
    result = await use_case.execute(_input_dto(fiber_g=8.0, ingredient_fiber_g=2.0), is_premium=True)
    assert result.fiber_g == 8.0
    assert result.ingredients[0].fiber_g == 2.0


async def test_free_user_gets_fiber_g_dropped():
    use_case = CreateFoodEntryUseCase(food_entries=FakeFoodEntryRepo())
    result = await use_case.execute(_input_dto(fiber_g=8.0, ingredient_fiber_g=2.0), is_premium=False)
    assert result.fiber_g is None
    assert result.ingredients[0].fiber_g is None


async def test_free_user_with_no_fiber_g_submitted_is_unaffected():
    use_case = CreateFoodEntryUseCase(food_entries=FakeFoodEntryRepo())
    result = await use_case.execute(_input_dto(), is_premium=False)
    assert result.fiber_g is None
    assert result.ingredients[0].fiber_g is None


async def test_get_returns_entry_for_its_owner():
    repo = FakeFoodEntryRepo()
    create_use_case = CreateFoodEntryUseCase(food_entries=repo)
    created = await create_use_case.execute(_input_dto(), is_premium=True)

    get_use_case = GetFoodEntryUseCase(food_entries=repo)
    result = await get_use_case.execute(user_id=1, entry_id=created.id)
    assert result.id == created.id


async def test_get_raises_not_found_for_another_users_entry():
    repo = FakeFoodEntryRepo()
    created = await CreateFoodEntryUseCase(food_entries=repo).execute(_input_dto(), is_premium=True)

    get_use_case = GetFoodEntryUseCase(food_entries=repo)
    with pytest.raises(FoodEntryNotFoundException):
        await get_use_case.execute(user_id=999, entry_id=created.id)
