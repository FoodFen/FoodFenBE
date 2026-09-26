"""Integration tests: SQLAlchemyPaymentRepository against a real PostgreSQL.

Requires a reachable database. Override with TEST_DATABASE_URL (or DATABASE_URL);
defaults to the dedicated ``foodfen_test`` database, never the dev ``foodfen`` one
— the schema here is dropped and recreated per test.
"""

from __future__ import annotations

import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.payment import Payment
from src.domain.entities.user import User
from src.domain.enums import PlanType
from src.infrastructure.db.base import Base
from src.infrastructure.db.models.payment_model import PaymentORM  # noqa: F401 — registers the table
from src.infrastructure.db.models.user_model import UserORM  # noqa: F401 — registers the table
from src.infrastructure.db.repositories.payment_repository import SQLAlchemyPaymentRepository
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
    user = await SQLAlchemyUserRepository(session).create(User.create(email="payer@example.com"))
    await session.commit()
    return user


async def test_create_assigns_a_unique_order_code(session):
    user = await _make_user(session)
    repo = SQLAlchemyPaymentRepository(session)

    first = await repo.create(Payment.create(user_id=user.id, plan_type=PlanType.MONTHLY, amount="49000"))
    second = await repo.create(Payment.create(user_id=user.id, plan_type=PlanType.MONTHLY, amount="49000"))
    await session.commit()

    assert first.order_code is not None
    assert second.order_code is not None
    assert first.order_code != second.order_code


async def test_get_by_order_code_round_trips(session):
    user = await _make_user(session)
    repo = SQLAlchemyPaymentRepository(session)
    created = await repo.create(
        Payment.create(user_id=user.id, plan_type=PlanType.ANNUAL, amount="499000")
    )
    await session.commit()

    fetched = await repo.get_by_order_code(created.order_code)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.plan_type is PlanType.ANNUAL


async def test_update_persists_status_change(session):
    user = await _make_user(session)
    repo = SQLAlchemyPaymentRepository(session)
    payment = await repo.create(
        Payment.create(user_id=user.id, plan_type=PlanType.MONTHLY, amount="49000")
    )
    await session.commit()

    payment.mark_paid()
    await repo.update(payment)
    await session.commit()

    fetched = await repo.get_by_order_code(payment.order_code)
    assert fetched is not None
    assert fetched.status.value == "paid"
