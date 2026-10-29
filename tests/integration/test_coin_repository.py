"""SQLAlchemyCoinRepository.list_page ordering/paging and get_by_client_id scoping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.application.chat_cursor import encode_cursor
from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.entities.user import User
from src.domain.enums import CoinReason
from src.infrastructure.db.base import Base
import src.infrastructure.db.models  # noqa: F401 — registers every table
from src.infrastructure.db.repositories.coin_repository import SQLAlchemyCoinRepository
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository

T0 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def _user(session, email: str) -> int:
    user = await SQLAlchemyUserRepository(session).create(User.create(email=email))
    return user.id


def _tx(user_id: int, n: int, at: datetime, client_id: str | None = None) -> CoinTransaction:
    return CoinTransaction(
        id=uuid4(),
        user_id=user_id,
        amount=n,
        reason=CoinReason.QUEST_COMPLETED,
        created_at=at,
        client_id=client_id,
    )


async def test_list_page_is_newest_first_and_pages_across_a_created_at_tie(session):
    me, other = await _user(session, "me@example.com"), await _user(session, "o@example.com")
    repo = SQLAlchemyCoinRepository(session)
    # amount 1 oldest; 2,3,4 tie on created_at (id desc breaks it); 5 newest; other user's row ignored.
    rows = [_tx(me, n, T0 + timedelta(days=d)) for n, d in [(1, 0), (2, 1), (3, 1), (4, 1), (5, 2)]]
    for row in rows:
        await repo.add(row)
    await repo.add(_tx(other, 9, T0 + timedelta(days=3)))
    tied = sorted(rows[1:4], key=lambda t: t.id, reverse=True)
    expected = [5, *(t.amount for t in tied), 1]

    assert [t.amount for t in await repo.list_page(me, None, 10)] == expected

    seen: list[int] = []
    before = None
    while page := await repo.list_page(me, before, 2):
        seen += [t.amount for t in page]
        before = encode_cursor(page[-1])
    assert seen == expected


async def test_get_by_client_id_is_scoped_to_the_user(session):
    me, other = await _user(session, "me@example.com"), await _user(session, "o@example.com")
    repo = SQLAlchemyCoinRepository(session)
    row = _tx(me, 1, T0, client_id="k1")
    await repo.add(row)

    found = await repo.get_by_client_id(me, "k1")
    assert found is not None and found.id == row.id
    assert await repo.get_by_client_id(other, "k1") is None
    assert await repo.get_by_client_id(me, "nope") is None
