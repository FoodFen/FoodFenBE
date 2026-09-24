"""Integration tests: ``create_idempotent`` against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL; defaults to the
``foodfen`` database from docker-compose. The schema is (re)created per test.
"""

from __future__ import annotations

import os

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.user import User
from src.domain.enums import InputMethod, MealType
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.food_entry_model import FoodEntryORM  # noqa: F401
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401
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


def _entry(user_id, client_id) -> FoodEntry:
    return FoodEntry.create(
        user_id=user_id,
        name="Meal",
        input_method=InputMethod.MANUAL,
        total_kcal=500,
        carbs_g=50.0,
        protein_g=30.0,
        fat_g=10.0,
        meal_type=MealType.LUNCH,
        client_id=client_id,
    )


async def test_a_conflicting_create_does_not_discard_other_pending_writes_in_the_session(session):
    """create_idempotent's conflict-recovery must only undo its own failed
    insert, not the whole request-scoped transaction — otherwise any
    endpoint that writes something else before calling create() (e.g. a
    quest reward) would silently lose that write whenever the create()
    happened to be a client_id retry."""
    user = await SQLAlchemyUserRepository(session).create(User.create(email="iso@example.com"))
    await session.commit()

    repo = SQLAlchemyFoodEntryRepository(session)
    first = await repo.create(_entry(user.id, "dup"))
    await session.commit()

    # A second, unrelated write pending in the same session before the
    # conflicting create() call below.
    unrelated = FoodEntryORM.from_domain(_entry(user.id, "unrelated"))
    session.add(unrelated)

    second = await repo.create(_entry(user.id, "dup"))  # same client_id -> conflict, recovers
    assert second.id == first.id

    await session.commit()

    fetched = (
        await session.execute(select(FoodEntryORM).where(FoodEntryORM.id == unrelated.id))
    ).scalar_one_or_none()
    assert fetched is not None
