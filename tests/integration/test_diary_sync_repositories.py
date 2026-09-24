"""Integration tests: the five diary-sync repositories against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL; defaults to the
``foodfen`` database from docker-compose. The schema is (re)created per test.
"""

from __future__ import annotations

import os
from datetime import date

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.activity_log import ActivityLog
from src.domain.entities.daily_goal import DailyGoal
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.user import User
from src.domain.entities.water_log import WaterLog
from src.domain.entities.weight_log import WeightLog
from src.domain.enums import InputMethod, MealType
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.activity_log_model import ActivityLogORM  # noqa: F401
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM  # noqa: F401
from src.infrastructure.db.models.food_entry_model import FoodEntryORM  # noqa: F401
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401
from src.infrastructure.db.models.water_log_model import WaterLogORM  # noqa: F401
from src.infrastructure.db.models.weight_log_model import WeightLogORM  # noqa: F401
from src.infrastructure.db.repositories.activity_log_repository import (
    SQLAlchemyActivityLogRepository,
)
from src.infrastructure.db.repositories.daily_goal_repository import SQLAlchemyDailyGoalRepository
from src.infrastructure.db.repositories.food_entry_repository import SQLAlchemyFoodEntryRepository
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.db.repositories.water_log_repository import SQLAlchemyWaterLogRepository
from src.infrastructure.db.repositories.weight_log_repository import SQLAlchemyWeightLogRepository

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


async def _make_two_users(session) -> tuple[User, User]:
    repo = SQLAlchemyUserRepository(session)
    a = await repo.create(User.create(email="a@example.com"))
    b = await repo.create(User.create(email="b@example.com"))
    await session.commit()
    return a, b


async def test_daily_goal_repository_lists_only_the_users_goals(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyDailyGoalRepository(session)

    from src.infrastructure.db.models.daily_goal_model import DailyGoalORM as _DailyGoalORM

    session.add(_DailyGoalORM.from_domain(
        DailyGoal.create(user_a.id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1))
    ))
    session.add(_DailyGoalORM.from_domain(
        DailyGoal.create(user_b.id, 1800, 180.0, 120.0, 50.0, 2000, date(2026, 1, 1))
    ))
    await session.flush()
    await session.commit()

    result = await repo.list_by_user(user_a.id)

    assert len(result) == 1
    assert result[0].target_kcal == 2000


async def test_food_entry_repository_list_by_date_range_is_inclusive_and_scoped(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyFoodEntryRepository(session)

    def _entry(user_id: int, logged_on: date) -> FoodEntry:
        return FoodEntry.create(
            user_id=user_id,
            name="Meal",
            input_method=InputMethod.MANUAL,
            total_kcal=500,
            carbs_g=50.0,
            protein_g=30.0,
            fat_g=10.0,
            meal_type=MealType.LUNCH,
            logged_on=logged_on,
        )

    await repo.create(_entry(user_a.id, date(2026, 1, 1)))  # lower boundary
    await repo.create(_entry(user_a.id, date(2026, 1, 31)))  # upper boundary
    await repo.create(_entry(user_a.id, date(2026, 2, 1)))  # outside range
    await repo.create(_entry(user_b.id, date(2026, 1, 15)))  # different user
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))

    assert len(result) == 2
    assert {e.logged_on for e in result} == {date(2026, 1, 1), date(2026, 1, 31)}


def _orm(entity):
    """Map any of the three simple log entities to its ORM row via its own from_domain."""
    from src.infrastructure.db.models.activity_log_model import ActivityLogORM
    from src.infrastructure.db.models.water_log_model import WaterLogORM
    from src.infrastructure.db.models.weight_log_model import WeightLogORM

    if isinstance(entity, ActivityLog):
        return ActivityLogORM.from_domain(entity)
    if isinstance(entity, WaterLog):
        return WaterLogORM.from_domain(entity)
    if isinstance(entity, WeightLog):
        return WeightLogORM.from_domain(entity)
    raise TypeError(type(entity))


async def test_activity_log_repository_list_by_date_range(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyActivityLogRepository(session)

    session.add(_orm(ActivityLog.create(user_a.id, "running", 300, logged_on=date(2026, 1, 15))))
    session.add(_orm(ActivityLog.create(user_b.id, "running", 300, logged_on=date(2026, 1, 15))))
    await session.flush()
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].user_id == user_a.id


async def test_water_log_repository_list_by_date_range(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyWaterLogRepository(session)

    session.add(_orm(WaterLog.create(user_a.id, 350, logged_on=date(2026, 1, 15))))
    session.add(_orm(WaterLog.create(user_b.id, 350, logged_on=date(2026, 1, 15))))
    await session.flush()
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].user_id == user_a.id


async def test_weight_log_repository_list_by_date_range(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyWeightLogRepository(session)

    session.add(_orm(WeightLog.create(user_a.id, 60.4, date(2026, 1, 15))))
    session.add(_orm(WeightLog.create(user_b.id, 60.4, date(2026, 1, 15))))
    await session.flush()
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].user_id == user_a.id
