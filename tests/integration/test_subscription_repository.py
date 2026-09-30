"""Integration tests: SQLAlchemySubscriptionRepository against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL (or DATABASE_URL);
defaults to the dedicated ``foodfen_test`` database, never the dev ``foodfen`` one
— the schema here is dropped and recreated per test.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User
from src.domain.enums import PlanType
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.subscription_model import SubscriptionORM  # noqa: F401
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401
from src.infrastructure.db.repositories.subscription_repository import (
    SQLAlchemySubscriptionRepository,
)
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
    user = await SQLAlchemyUserRepository(session).create(
        User.create(email="subscriber@example.com")
    )
    await session.commit()
    return user


async def test_save_inserts_when_none_exists(session):
    user = await _make_user(session)
    repo = SQLAlchemySubscriptionRepository(session)
    sub = Subscription.create(
        user_id=user.id,
        plan_type=PlanType.MONTHLY,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        price=Decimal("49000"),
    )

    saved = await repo.save(sub)
    await session.commit()

    fetched = await repo.get_by_user_id(user.id)
    assert fetched is not None
    assert fetched.id == saved.id


async def test_save_updates_the_single_row_per_user(session):
    user = await _make_user(session)
    repo = SQLAlchemySubscriptionRepository(session)
    first = Subscription.create(
        user_id=user.id,
        plan_type=PlanType.MONTHLY,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        price=Decimal("49000"),
    )
    await repo.save(first)
    await session.commit()

    renewed = Subscription.renew(first, user.id, PlanType.MONTHLY, Decimal("49000"), date(2026, 1, 20))
    await repo.save(renewed)
    await session.commit()

    fetched = await repo.get_by_user_id(user.id)
    assert fetched is not None
    assert fetched.id == first.id  # same row, not a second one
    assert fetched.start_date == date(2026, 1, 1)
    assert fetched.end_date == date(2026, 3, 2)


async def test_expiry_sweep_expires_lapsed_and_downgrades_user(session):
    from src.domain.enums import SubscriptionStatus, SubscriptionTier
    from src.infrastructure.expiry_job import expire_lapsed_subscriptions

    lapsed = await _make_user(session)
    lapsed.subscription_tier = SubscriptionTier.PREMIUM
    await SQLAlchemyUserRepository(session).update(lapsed)
    repo = SQLAlchemySubscriptionRepository(session)
    await repo.save(
        Subscription.create(lapsed.id, PlanType.MONTHLY, date(2026, 1, 1), date(2026, 2, 1), 49000)
    )
    await session.commit()

    assert await expire_lapsed_subscriptions(session, date(2026, 2, 2)) == 1
    await session.commit()
    assert (await repo.get_by_user_id(lapsed.id)).status is SubscriptionStatus.EXPIRED
    assert (await SQLAlchemyUserRepository(session).get_by_id(lapsed.id)).subscription_tier is (
        SubscriptionTier.FREE
    )
    assert await expire_lapsed_subscriptions(session, date(2026, 2, 2)) == 0  # idempotent
