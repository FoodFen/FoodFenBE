"""GetUserUseCase unit tests: in-memory repository, no DB, no FastAPI."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.application.use_cases.get_user import GetUserUseCase
from src.domain.entities.user import User
from src.domain.exceptions import UserNotFoundException


class InMemoryUserRepository:
    """Satisfies UserRepositoryProtocol structurally."""

    def __init__(self) -> None:
        self._by_id: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self._by_id.get(user_id)

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._by_id.values() if u.email == email), None)

    async def create(self, user: User) -> User:
        self._by_id[user.id] = user
        return user


async def test_get_user_returns_existing():
    repo = InMemoryUserRepository()
    user = User.create(email="bob@example.com", name="Bob")
    await repo.create(user)

    out = await GetUserUseCase(repo).execute(user.id)
    assert out.id == user.id
    assert out.email == "bob@example.com"


async def test_get_user_missing_raises():
    with pytest.raises(UserNotFoundException):
        await GetUserUseCase(InMemoryUserRepository()).execute(uuid4())
