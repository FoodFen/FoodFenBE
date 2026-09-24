"""CreateFoodEntryUseCase / GetFoodEntryUseCase / ListFoodEntriesUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

import pytest

from src.application.dtos.food_entry import CreateFoodEntryInputDTO, CreateIngredientInputDTO
from src.application.use_cases.create_food_entry import CreateFoodEntryUseCase
from src.application.use_cases.get_food_entry import GetFoodEntryUseCase
from src.application.use_cases.list_food_entries import ListFoodEntriesUseCase
from src.domain.entities.food_entry import FoodEntry
from src.domain.enums import InputMethod, MealType
from src.domain.exceptions import FoodEntryNotFoundException


class FakeFoodEntryRepo:
    def __init__(self) -> None:
        self._by_id: dict = {}

    async def create(self, entry: FoodEntry) -> FoodEntry:
        self._by_id[entry.id] = entry
        return entry

    async def get_by_id(self, entry_id):
        return self._by_id.get(entry_id)

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            e
            for e in self._by_id.values()
            if e.user_id == user_id and from_date <= e.logged_on <= to_date
        ]


def _input_dto(fiber_g=None, ingredient_fiber_g=None, meal_type=MealType.LUNCH) -> CreateFoodEntryInputDTO:
    return CreateFoodEntryInputDTO(
        user_id=1,
        name="Grilled chicken with rice",
        input_method=InputMethod.MANUAL,
        total_kcal=650,
        carbs_g=70.0,
        protein_g=45.0,
        fat_g=15.0,
        meal_type=meal_type,
        client_id="entry_1",
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


async def test_fiber_g_is_always_stored_regardless_of_tier():
    """Premium gates fiber_g *display* client-side only — the server never
    drops it, or a free user who later upgrades permanently loses data they
    already logged (mirrors ai-food-capture.md's "no Premium check" rule)."""
    use_case = CreateFoodEntryUseCase(food_entries=FakeFoodEntryRepo())
    result = await use_case.execute(_input_dto(fiber_g=8.0, ingredient_fiber_g=2.0))
    assert result.fiber_g == 8.0
    assert result.ingredients[0].fiber_g == 2.0


async def test_fiber_g_stays_none_when_not_submitted():
    use_case = CreateFoodEntryUseCase(food_entries=FakeFoodEntryRepo())
    result = await use_case.execute(_input_dto())
    assert result.fiber_g is None
    assert result.ingredients[0].fiber_g is None


async def test_create_result_carries_user_id_meal_type_and_ingredient_food_entry_id():
    use_case = CreateFoodEntryUseCase(food_entries=FakeFoodEntryRepo())
    result = await use_case.execute(_input_dto(meal_type=MealType.BREAKFAST))
    assert result.user_id == 1
    assert result.meal_type is MealType.BREAKFAST
    assert result.ingredients[0].food_entry_id == result.id


async def test_submitted_logged_on_is_stored_exactly_not_derived_from_logged_at():
    """logged_on is the user's local calendar day — the server must never
    derive it from logged_at (a UTC instant), or a user near UTC midnight
    (e.g. Vietnam, UTC+7) permanently gets the wrong day stored."""
    use_case = CreateFoodEntryUseCase(food_entries=FakeFoodEntryRepo())
    explicit_day = date(2026, 1, 1)
    input_dto = CreateFoodEntryInputDTO(
        user_id=1,
        name="Late-night snack",
        input_method=InputMethod.MANUAL,
        total_kcal=200,
        carbs_g=20.0,
        protein_g=5.0,
        fat_g=5.0,
        meal_type=MealType.SNACK,
        client_id="entry_1",
        logged_on=explicit_day,
    )
    result = await use_case.execute(input_dto)
    assert result.logged_on == explicit_day


async def test_get_returns_entry_for_its_owner():
    repo = FakeFoodEntryRepo()
    create_use_case = CreateFoodEntryUseCase(food_entries=repo)
    created = await create_use_case.execute(_input_dto())

    get_use_case = GetFoodEntryUseCase(food_entries=repo)
    result = await get_use_case.execute(user_id=1, entry_id=created.id)
    assert result.id == created.id


async def test_get_raises_not_found_for_another_users_entry():
    repo = FakeFoodEntryRepo()
    created = await CreateFoodEntryUseCase(food_entries=repo).execute(_input_dto())

    get_use_case = GetFoodEntryUseCase(food_entries=repo)
    with pytest.raises(FoodEntryNotFoundException):
        await get_use_case.execute(user_id=999, entry_id=created.id)


async def test_list_returns_empty_when_nothing_in_range():
    repo = FakeFoodEntryRepo()
    use_case = ListFoodEntriesUseCase(food_entries=repo)
    result = await use_case.execute(user_id=1, from_date=date(2026, 1, 1), to_date=date(2026, 1, 31))
    assert result == []


async def test_list_returns_entries_created_via_the_create_use_case():
    repo = FakeFoodEntryRepo()
    created = await CreateFoodEntryUseCase(food_entries=repo).execute(_input_dto())

    use_case = ListFoodEntriesUseCase(food_entries=repo)
    result = await use_case.execute(
        user_id=1, from_date=created.logged_on, to_date=created.logged_on
    )

    assert [r.id for r in result] == [created.id]
