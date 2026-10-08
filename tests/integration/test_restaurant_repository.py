"""SQLAlchemyRestaurantRepository against the test database."""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import src.infrastructure.db.models  # noqa: F401 — registers every table
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.entities.user import User
from src.domain.enums import ModerationStatus, ReviewDecision
from src.domain.exceptions import RestaurantAlreadyExistsException
from src.infrastructure.db.base import Base
from src.infrastructure.db.repositories.restaurant_repository import SQLAlchemyRestaurantRepository
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
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _owner(session, email="owner@example.com") -> int:
    user = await SQLAlchemyUserRepository(session).create(User.create(email=email, name="Owner"))
    return user.id


def _restaurant(user_id: int, name: str = "Quán Ngon") -> Restaurant:
    return Restaurant.create(
        user_id=user_id, name=name, address="1 Lê Lợi", phone="0901",
        opening_hours="7-21", latitude=10.7, longitude=106.7,
    )


def _dish(restaurant_id) -> Dish:
    return Dish.create(
        restaurant_id=restaurant_id, name="Phở", price=Decimal("55000"), serving_g=500,
        kcal=450, protein_g=30, carbs_g=55, fat_g=12,
    )


async def test_round_trip_restaurant_and_dish(session):
    repo = SQLAlchemyRestaurantRepository(session)
    restaurant = _restaurant(await _owner(session))
    await repo.add(restaurant)
    dish = _dish(restaurant.id)
    await repo.add_dish(dish)

    loaded = await repo.get_by_owner(restaurant.user_id)
    assert loaded is not None and loaded.id == restaurant.id
    assert [d.id for d in await repo.list_dishes(restaurant.id)] == [dish.id]
    assert (await repo.get_dish(dish.id)).price == Decimal("55000")

    loaded.review(ReviewDecision.APPROVED, None, loaded.updated_at)
    await repo.update(loaded)
    assert (await repo.get_by_id(restaurant.id)).status == ModerationStatus.APPROVED

    await repo.delete_dish(dish.id)
    assert await repo.list_dishes(restaurant.id) == []


async def test_add_duplicate_owner_raises_already_exists(session):
    repo = SQLAlchemyRestaurantRepository(session)
    owner = await _owner(session)
    await repo.add(_restaurant(owner))
    with pytest.raises(RestaurantAlreadyExistsException):
        await repo.add(_restaurant(owner, name="Second"))
