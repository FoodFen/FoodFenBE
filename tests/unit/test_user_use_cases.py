"""Use-case unit tests: in-memory repository, no DB, no FastAPI."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from src.application.dtos.user import CreateUserInputDTO
from src.application.use_cases.create_user import CreateUserUseCase
from src.application.use_cases.get_user import GetUserUseCase
from src.domain.entities.user import User
from src.domain.exceptions import (
    InvalidUserAttributeException,
    UserAlreadyExistsException,
    UserNotFoundException,
)


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


async def test_create_user_normalizes_and_persists():
    repo = InMemoryUserRepository()
    out = await CreateUserUseCase(repo).execute(CreateUserInputDTO(email="  Alice@Example.COM ", name="  Alice  "))

    assert out.email == "alice@example.com"
    assert out.name == "Alice"
    assert out.is_active is True
    assert await repo.get_by_id(out.id) is not None


async def test_create_user_rejects_duplicate_email():
    repo = InMemoryUserRepository()
    uc = CreateUserUseCase(repo)
    await uc.execute(CreateUserInputDTO(email="dup@example.com", name="One"))

    with pytest.raises(UserAlreadyExistsException):
        await uc.execute(CreateUserInputDTO(email="dup@example.com", name="Two"))


async def test_create_user_rejects_invalid_email():
    with pytest.raises(InvalidUserAttributeException):
        await CreateUserUseCase(InMemoryUserRepository()).execute(
            CreateUserInputDTO(email="not-an-email", name="X")
        )


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
