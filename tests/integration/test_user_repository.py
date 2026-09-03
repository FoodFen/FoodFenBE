"""Integration tests: SQLAlchemyUserRepository against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL; defaults to the
``foodfen`` database from docker-compose. The schema is (re)created per test.
"""

from __future__ import annotations

import os
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.user import User
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401 — registers the table
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


async def test_create_then_get_by_id(session):
    repo = SQLAlchemyUserRepository(session)
    created = await repo.create(User.create(email="int@example.com", name="Integration"))
    await session.commit()

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.email == "int@example.com"


async def test_get_by_email(session):
    repo = SQLAlchemyUserRepository(session)
    await repo.create(User.create(email="byemail@example.com", name="ByEmail"))
    await session.commit()

    assert await repo.get_by_email("byemail@example.com") is not None
    assert await repo.get_by_email("missing@example.com") is None


async def test_get_by_id_missing_returns_none(session):
    repo = SQLAlchemyUserRepository(session)
    assert await repo.get_by_id(uuid4()) is None
