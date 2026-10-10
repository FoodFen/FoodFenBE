"""Startup bootstrap (ensure_admin / seed_demo) against the test database."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import src.infrastructure.db.models  # noqa: F401 — registers every table
from src.domain.entities.user import User
from src.domain.enums import ModerationStatus, UserRole
from src.domain.exceptions import WeakPasswordException
from src.infrastructure.db.base import Base
from src.infrastructure.db.bootstrap import ensure_admin, seed_demo
from src.infrastructure.db.models.restaurant_model import RestaurantORM
from src.infrastructure.db.models.user_model import UserORM
from src.infrastructure.db.repositories.restaurant_repository import SQLAlchemyRestaurantRepository
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository
from src.infrastructure.security.password_hasher import BcryptPasswordHasher

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


async def _user_count(session) -> int:
    return await session.scalar(select(func.count(UserORM.id)))


async def test_ensure_admin_creates_admin_with_working_password(session):
    await ensure_admin(session, "Boss@Example.com", "s3cret-pass")

    boss = await SQLAlchemyUserRepository(session).get_by_email("boss@example.com")
    assert boss.role == UserRole.ADMIN
    assert BcryptPasswordHasher().verify("s3cret-pass", boss.password_hash)


async def test_ensure_admin_promotes_existing_user_and_keeps_password(session):
    users = SQLAlchemyUserRepository(session)
    original = await users.create(User.create(email="boss@example.com", password_hash="old-hash"))

    await ensure_admin(session, "boss@example.com", "another-pass")

    boss = await users.get_by_email("boss@example.com")
    assert boss.id == original.id and boss.role == UserRole.ADMIN
    assert boss.password_hash == "old-hash"


async def test_ensure_admin_twice_is_a_noop(session):
    await ensure_admin(session, "boss@example.com", "s3cret-pass")
    await ensure_admin(session, "boss@example.com", "s3cret-pass")

    assert await _user_count(session) == 1


async def test_ensure_admin_rejects_weak_password(session):
    with pytest.raises(WeakPasswordException):
        await ensure_admin(session, "boss@example.com", "short")

    assert await _user_count(session) == 0


async def test_seed_demo_twice_does_not_duplicate(session):
    await seed_demo(session)
    await seed_demo(session)

    public = await SQLAlchemyRestaurantRepository(session).list_public_dishes()
    assert len({r.id for _, r in public}) == 3 and len(public) == 15
    assert all(r.status == d.status == ModerationStatus.APPROVED for d, r in public)
    assert await session.scalar(select(func.count(RestaurantORM.id))) == 3
