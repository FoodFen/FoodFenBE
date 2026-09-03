"""Persistence port for users. Structural typing via Protocol — no ABC, no framework."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.entities.user import User


class UserRepositoryProtocol(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def create(self, user: User) -> User: ...

    async def update(self, user: User) -> User:
        """Persist changes to an existing user. Raise ``UserNotFoundException`` if it is gone."""
        ...
