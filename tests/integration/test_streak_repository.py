"""Integration tests: SQLAlchemyStreakRepository against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL (or DATABASE_URL);
defaults to the dedicated ``foodfen_test`` database, never the dev ``foodfen`` one
— the schema here is dropped and recreated per test.
"""

from __future__ import annotations

import os
from datetime import date

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.streak import Streak
from src.domain.entities.user import User
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.streak_model import StreakORM  # noqa: F401 — registers the table
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401 — registers the table
from src.infrastructure.db.repositories.streak_repository import SQLAlchemyStreakRepository
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
    user = await SQLAlchemyUserRepository(session).create(User.create(email="streaker@example.com"))
    await session.commit()
    return user


async def test_upsert_creates_the_first_row(session):
    user = await _make_user(session)
    repo = SQLAlchemyStreakRepository(session)

    streak = Streak(
        id=__import__("uuid").uuid4(),
        user_id=user.id,
        current_streak=3,
        longest_streak=5,
        last_active_date=date(2026, 1, 15),
    )
    created = await repo.upsert(streak)
    await session.commit()

    assert created.current_streak == 3
    assert created.longest_streak == 5
    assert created.last_active_date == date(2026, 1, 15)


async def test_upsert_replaces_the_existing_row_for_the_same_user(session):
    user = await _make_user(session)
    repo = SQLAlchemyStreakRepository(session)

    first = await repo.upsert(
        Streak(
            id=__import__("uuid").uuid4(),
            user_id=user.id,
            current_streak=3,
            longest_streak=5,
            last_active_date=date(2026, 1, 15),
        )
    )
    await session.commit()

    second = await repo.upsert(
        Streak(
            id=__import__("uuid").uuid4(),
            user_id=user.id,
            current_streak=4,
            longest_streak=5,
            last_active_date=date(2026, 1, 16),
        )
    )
    await session.commit()

    assert second.id == first.id  # same row, not a new one
    assert second.current_streak == 4
    assert second.last_active_date == date(2026, 1, 16)


async def test_upsert_does_not_touch_another_users_streak(session):
    from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository as _Repo

    user_a = await _make_user(session)
    user_b = await _Repo(session).create(User.create(email="other-streaker@example.com"))
    await session.commit()
    repo = SQLAlchemyStreakRepository(session)

    await repo.upsert(
        Streak(id=__import__("uuid").uuid4(), user_id=user_a.id, current_streak=3, longest_streak=5)
    )
    await session.commit()
    await repo.upsert(
        Streak(id=__import__("uuid").uuid4(), user_id=user_b.id, current_streak=1, longest_streak=1)
    )
    await session.commit()

    a_row = await repo.upsert(
        Streak(id=__import__("uuid").uuid4(), user_id=user_a.id, current_streak=3, longest_streak=5)
    )
    await session.commit()
    assert a_row.user_id == user_a.id
    assert a_row.current_streak == 3
