"""scripts.make_admin / scripts.seed_demo core functions against the test database."""

from __future__ import annotations

import os

import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import src.infrastructure.db.models  # noqa: F401 — registers every table
from scripts import make_admin, seed_demo
from src.domain.entities.user import User
from src.domain.enums import ModerationStatus, UserRole
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.dish_model import DishORM
from src.infrastructure.db.models.restaurant_model import RestaurantORM
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


async def test_seed_demo_is_idempotent_and_removable(session):
    await seed_demo.run(session)
    public = await SQLAlchemyRestaurantRepository(session).list_public_dishes()
    assert len({r.id for _, r in public}) == 3 and len(public) == 15
    assert all(r.status == d.status == ModerationStatus.APPROVED for d, r in public)

    again = await seed_demo.run(session)
    assert all(line.endswith("exists") for line in again)
    assert await session.scalar(select(func.count(RestaurantORM.id))) == 3

    assert await seed_demo.run(session, remove=True) == ["removed 3 demo users, 3 restaurants, 15 dishes"]
    assert await session.scalar(select(func.count(RestaurantORM.id))) == 0
    assert await session.scalar(select(func.count(DishORM.id))) == 0


async def test_make_admin_promote_revoke_and_unknown(session):
    users = SQLAlchemyUserRepository(session)
    await users.create(User.create(email="boss@example.com", name="Boss"))

    out = await make_admin.run(session, ["BOSS@example.com", "nobody@example.com"])
    assert out == ["BOSS@example.com: promoted", "nobody@example.com: not found (sign up first)"]
    assert (await users.get_by_email("boss@example.com")).role == UserRole.ADMIN
    assert await make_admin.run(session, ["boss@example.com"]) == ["boss@example.com: already admin"]

    assert await make_admin.run(session, ["boss@example.com"], revoke=True) == ["boss@example.com: revoked"]
    assert (await users.get_by_email("boss@example.com")).role == UserRole.USER
