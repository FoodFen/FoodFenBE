"""Integration tests: SQLAlchemyFoodEntryRepository against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL; defaults to the
``foodfen`` database from docker-compose. The schema is (re)created per test.
"""

from __future__ import annotations

import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient
from src.domain.entities.user import User
from src.domain.enums import InputMethod, MealType
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
    "postgresql+asyncpg://postgres:postgres@localhost:5433/foodfen",
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
