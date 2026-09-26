"""Integration tests: the five diary-sync repositories against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL (or DATABASE_URL);
defaults to the dedicated ``foodfen_test`` database, never the dev ``foodfen`` one
— the schema here is dropped and recreated per test.
"""

from __future__ import annotations

import os
from datetime import date
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.activity_log import ActivityLog
from src.domain.entities.daily_goal import DailyGoal
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.user import User
from src.domain.entities.water_log import WaterLog
from src.domain.entities.weight_log import WeightLog
from src.domain.enums import ActivitySource, InputMethod, MealType
from src.domain.exceptions import ActivityLogNotFoundException, WaterLogNotFoundException
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
        DailyGoal.create(user_a.id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1), client_id="goal_1")
    ))
    session.add(_DailyGoalORM.from_domain(
        DailyGoal.create(user_b.id, 1800, 180.0, 120.0, 50.0, 2000, date(2026, 1, 1), client_id="goal_1")
    ))
    await session.flush()
    await session.commit()

    result = await repo.list_by_user(user_a.id)

    assert len(result) == 1
    assert result[0].target_kcal == 2000


async def test_daily_goal_repository_lists_in_effective_date_order(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyDailyGoalRepository(session)

    await repo.create(
        DailyGoal.create(user_a.id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 3, 1), client_id="g3")
    )
    await session.commit()
    await repo.create(
        DailyGoal.create(user_a.id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1), client_id="g1")
    )
    await session.commit()
    await repo.create(
        DailyGoal.create(user_a.id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 2, 1), client_id="g2")
    )
    await session.commit()

    result = await repo.list_by_user(user_a.id)

    assert [g.effective_date for g in result] == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]


async def test_daily_goal_repository_create_upserts_replacing_values_for_a_second_goal_same_day(
    session,
):
    """One row per (user, effective_date) — changing today's target again in
    the same sitting replaces that row's values rather than erroring or
    silently no-opping (per the FE contract: CLAUDE.md's actual invariant is
    that changing today's target never rewrites *last week's* row, not that
    today's row can never change)."""
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyDailyGoalRepository(session)

    first = await repo.create(
        DailyGoal.create(user_a.id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1), client_id="g1")
    )
    await session.commit()

    second = await repo.create(
        DailyGoal.create(
            user_a.id, 1800, 180.0, 120.0, 50.0, 2000, date(2026, 1, 1), client_id="g2"
        )
    )
    await session.commit()

    assert second.id == first.id
    assert second.target_kcal == 1800

    result = await repo.list_by_user(user_a.id)
    assert len(result) == 1


async def test_daily_goal_repository_create_with_repeated_client_id_and_date_replaces_values(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyDailyGoalRepository(session)

    first = await repo.create(
        DailyGoal.create(user_a.id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1), client_id="dup")
    )
    await session.commit()
    second = await repo.create(
        DailyGoal.create(user_a.id, 1800, 180.0, 120.0, 50.0, 2000, date(2026, 1, 1), client_id="dup")
    )
    await session.commit()

    assert second.id == first.id
    assert second.target_kcal == 1800


async def test_food_entry_repository_list_by_date_range_is_inclusive_and_scoped(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyFoodEntryRepository(session)

    def _entry(user_id: int, logged_on: date, client_id: str) -> FoodEntry:
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
            logged_on=logged_on,
        )

    await repo.create(_entry(user_a.id, date(2026, 1, 1), "entry_1"))  # lower boundary
    await repo.create(_entry(user_a.id, date(2026, 1, 31), "entry_2"))  # upper boundary
    await repo.create(_entry(user_a.id, date(2026, 2, 1), "entry_3"))  # outside range
    await repo.create(_entry(user_b.id, date(2026, 1, 15), "entry_1"))  # different user
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


async def test_activity_log_repository_list_by_date_range_is_inclusive_and_scoped(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyActivityLogRepository(session)

    session.add(_orm(ActivityLog.create(
        user_a.id, "running", 300, client_id="activity_1", logged_on=date(2026, 1, 1)
    )))
    session.add(_orm(ActivityLog.create(
        user_a.id, "running", 300, client_id="activity_2", logged_on=date(2026, 1, 31)
    )))
    session.add(_orm(ActivityLog.create(
        user_a.id, "running", 300, client_id="activity_3", logged_on=date(2026, 2, 1)
    )))
    session.add(_orm(ActivityLog.create(
        user_b.id, "running", 300, client_id="activity_1", logged_on=date(2026, 1, 15)
    )))
    await session.flush()
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))

    assert len(result) == 2
    assert {log.logged_on for log in result} == {date(2026, 1, 1), date(2026, 1, 31)}
    assert all(log.user_id == user_a.id for log in result)


async def test_water_log_repository_list_by_date_range_is_inclusive_and_scoped(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyWaterLogRepository(session)

    session.add(_orm(WaterLog.create(user_a.id, 350, client_id="water_1", logged_on=date(2026, 1, 1))))
    session.add(_orm(WaterLog.create(user_a.id, 350, client_id="water_2", logged_on=date(2026, 1, 31))))
    session.add(_orm(WaterLog.create(user_a.id, 350, client_id="water_3", logged_on=date(2026, 2, 1))))
    session.add(_orm(WaterLog.create(user_b.id, 350, client_id="water_1", logged_on=date(2026, 1, 15))))
    await session.flush()
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))

    assert len(result) == 2
    assert {log.logged_on for log in result} == {date(2026, 1, 1), date(2026, 1, 31)}
    assert all(log.user_id == user_a.id for log in result)


async def test_weight_log_repository_list_by_date_range_is_inclusive_and_scoped(session):
    user_a, user_b = await _make_two_users(session)
    repo = SQLAlchemyWeightLogRepository(session)

    session.add(_orm(WeightLog.create(user_a.id, 60.4, date(2026, 1, 1), client_id="weight_1")))
    session.add(_orm(WeightLog.create(user_a.id, 60.4, date(2026, 1, 31), client_id="weight_2")))
    session.add(_orm(WeightLog.create(user_a.id, 60.4, date(2026, 2, 1), client_id="weight_3")))
    session.add(_orm(WeightLog.create(user_b.id, 60.4, date(2026, 1, 15), client_id="weight_1")))
    await session.flush()
    await session.commit()

    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 31))

    assert len(result) == 2
    assert {log.recorded_at for log in result} == {date(2026, 1, 1), date(2026, 1, 31)}
    assert all(log.user_id == user_a.id for log in result)


async def test_activity_log_repository_create_is_idempotent_on_client_id(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyActivityLogRepository(session)

    first = await repo.create(
        ActivityLog.create(user_a.id, "running", 300, client_id="dup", logged_on=date(2026, 1, 1))
    )
    await session.commit()
    second = await repo.create(
        ActivityLog.create(user_a.id, "cycling", 999, client_id="dup", logged_on=date(2026, 1, 2))
    )
    await session.commit()

    assert second.id == first.id
    assert second.activity_type == "running"  # unchanged: the retry was ignored, not applied


async def test_activity_log_repository_update_replaces_fields(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyActivityLogRepository(session)
    created = await repo.create(
        ActivityLog.create(user_a.id, "running", 300, client_id="a1", logged_on=date(2026, 1, 1))
    )
    await session.commit()

    replacement = ActivityLog(
        id=created.id,
        user_id=user_a.id,
        activity_type="swimming",
        calories_burned=450,
        client_id=created.client_id,
        source=ActivitySource.MANUAL,
        logged_at=created.logged_at,
        logged_on=created.logged_on,
    )
    updated = await repo.update(replacement)
    await session.commit()

    assert updated.activity_type == "swimming"
    assert updated.calories_burned == 450


async def test_activity_log_repository_update_raises_not_found_for_a_missing_log(session):
    repo = SQLAlchemyActivityLogRepository(session)
    ghost = ActivityLog(
        id=uuid4(), user_id=1, activity_type="running", calories_burned=100, client_id="ghost"
    )
    with pytest.raises(ActivityLogNotFoundException):
        await repo.update(ghost)


async def test_activity_log_repository_get_by_id_round_trips(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyActivityLogRepository(session)
    created = await repo.create(
        ActivityLog.create(user_a.id, "running", 300, client_id="a1", logged_on=date(2026, 1, 1))
    )
    await session.commit()

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.activity_type == "running"

    assert await repo.get_by_id(uuid4()) is None


async def test_weight_log_repository_create_is_idempotent_on_client_id(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyWeightLogRepository(session)

    first = await repo.create(WeightLog.create(user_a.id, 60.4, date(2026, 1, 1), client_id="dup"))
    await session.commit()
    second = await repo.create(WeightLog.create(user_a.id, 99.9, date(2026, 1, 2), client_id="dup"))
    await session.commit()

    assert second.id == first.id
    assert second.weight == 60.4  # unchanged: the retry was ignored


async def test_water_log_repository_create_is_idempotent_on_client_id(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyWaterLogRepository(session)

    first = await repo.create(
        WaterLog.create(user_a.id, 350, client_id="dup", logged_on=date(2026, 1, 1))
    )
    await session.commit()
    second = await repo.create(
        WaterLog.create(user_a.id, 999, client_id="dup", logged_on=date(2026, 1, 2))
    )
    await session.commit()

    assert second.id == first.id
    assert second.amount_ml == 350  # unchanged: the retry was ignored


async def test_water_log_repository_delete_soft_deletes_and_list_stops_returning_it(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyWaterLogRepository(session)
    created = await repo.create(
        WaterLog.create(user_a.id, 350, client_id="w1", logged_on=date(2026, 1, 1))
    )
    await session.commit()

    await repo.delete(created.id)
    await session.commit()

    assert await repo.get_by_id(created.id) is None
    result = await repo.list_by_date_range(user_a.id, date(2026, 1, 1), date(2026, 1, 1))
    assert result == []


async def test_water_log_repository_delete_twice_raises_not_found(session):
    user_a, _ = await _make_two_users(session)
    repo = SQLAlchemyWaterLogRepository(session)
    created = await repo.create(
        WaterLog.create(user_a.id, 350, client_id="w1", logged_on=date(2026, 1, 1))
    )
    await session.commit()
    await repo.delete(created.id)
    await session.commit()

    with pytest.raises(WaterLogNotFoundException):
        await repo.delete(created.id)
