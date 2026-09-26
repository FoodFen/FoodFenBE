"""Integration tests: SQLAlchemyFoodEntryRepository against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL (or DATABASE_URL);
defaults to the dedicated ``foodfen_test`` database, never the dev ``foodfen`` one
— the schema here is dropped and recreated per test.
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient
from src.domain.entities.user import User
from src.domain.enums import InputMethod, MealType
from src.domain.exceptions import FoodEntryNotFoundException
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.food_entry_model import (  # noqa: F401 — registers the tables
    FoodEntryORM,
    IngredientORM,
)
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401 — registers the table
from src.infrastructure.db.repositories.food_entry_repository import SQLAlchemyFoodEntryRepository
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen_test"),
)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _make_user(session) -> User:
    user = await SQLAlchemyUserRepository(session).create(User.create(email="eater@example.com"))
    await session.commit()
    return user


def _entry_with_ingredients(user_id: int) -> FoodEntry:
    entry = FoodEntry.create(
        user_id=user_id,
        name="Post-workout lunch",
        input_method=InputMethod.MANUAL,
        total_kcal=520,
        carbs_g=45.0,
        protein_g=30.0,
        fat_g=22.5,
        meal_type=MealType.LUNCH,
        client_id="entry_1",
        fiber_g=6.0,
    )
    entry.ingredients = [
        Ingredient.create(entry.id, "chicken breast", 150.0, 250, 0.0, 46.0, 5.4, fiber_g=0.0),
        Ingredient.create(entry.id, "brown rice", 120.0, 140, 30.0, 3.0, 1.1),
    ]
    return entry


async def test_create_cascades_ingredients(session):
    user = await _make_user(session)
    repo = SQLAlchemyFoodEntryRepository(session)

    created = await repo.create(_entry_with_ingredients(user.id))
    await session.commit()

    assert len(created.ingredients) == 2


async def test_get_by_id_round_trips_with_ingredients(session):
    user = await _make_user(session)
    repo = SQLAlchemyFoodEntryRepository(session)
    created = await repo.create(_entry_with_ingredients(user.id))
    await session.commit()

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.user_id == user.id
    assert [i.name for i in fetched.ingredients] == ["chicken breast", "brown rice"]
    assert fetched.fiber_g == 6.0


async def test_get_by_id_missing_returns_none(session):
    repo = SQLAlchemyFoodEntryRepository(session)
    from uuid import uuid4

    assert await repo.get_by_id(uuid4()) is None


async def test_create_with_a_repeated_client_id_returns_the_existing_row_not_a_duplicate(session):
    user = await _make_user(session)
    repo = SQLAlchemyFoodEntryRepository(session)

    first = await repo.create(_entry_with_ingredients(user.id))
    await session.commit()

    retry = _entry_with_ingredients(user.id)  # same client_id="entry_1", different id
    second = await repo.create(retry)
    await session.commit()

    assert second.id == first.id
    rows = (
        await session.execute(select(func.count()).select_from(FoodEntryORM))
    ).scalar_one()
    assert rows == 1


async def test_update_replaces_scalar_fields_and_ingredients(session):
    user = await _make_user(session)
    repo = SQLAlchemyFoodEntryRepository(session)
    created = await repo.create(_entry_with_ingredients(user.id))
    await session.commit()

    replacement = FoodEntry(
        id=created.id,
        user_id=user.id,
        name="Different meal",
        input_method=InputMethod.MANUAL,
        total_kcal=800,
        carbs_g=90.0,
        protein_g=50.0,
        fat_g=20.0,
        meal_type=MealType.DINNER,
        client_id=created.client_id,
        ingredients=[Ingredient.create(created.id, "tofu", 100.0, 80, 5.0, 8.0, 4.0)],
    )
    updated = await repo.update(replacement)
    await session.commit()

    assert updated.name == "Different meal"
    assert updated.meal_type == MealType.DINNER
    assert [i.name for i in updated.ingredients] == ["tofu"]


async def test_update_raises_not_found_for_a_missing_entry(session):
    from uuid import uuid4

    repo = SQLAlchemyFoodEntryRepository(session)
    ghost = FoodEntry(
        id=uuid4(),
        user_id=1,
        name="Ghost",
        input_method=InputMethod.MANUAL,
        total_kcal=1,
        carbs_g=1.0,
        protein_g=1.0,
        fat_g=1.0,
        meal_type=MealType.SNACK,
        client_id="ghost",
    )
    with pytest.raises(FoodEntryNotFoundException):
        await repo.update(ghost)


async def test_delete_soft_deletes_and_get_by_id_stops_returning_it(session):
    user = await _make_user(session)
    repo = SQLAlchemyFoodEntryRepository(session)
    created = await repo.create(_entry_with_ingredients(user.id))
    await session.commit()

    await repo.delete(created.id)
    await session.commit()

    assert await repo.get_by_id(created.id) is None


async def test_delete_on_an_already_deleted_entry_raises_not_found(session):
    user = await _make_user(session)
    repo = SQLAlchemyFoodEntryRepository(session)
    created = await repo.create(_entry_with_ingredients(user.id))
    await session.commit()
    await repo.delete(created.id)
    await session.commit()

    with pytest.raises(FoodEntryNotFoundException):
        await repo.delete(created.id)
