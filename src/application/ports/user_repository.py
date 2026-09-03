"""Persistence port for users. Structural typing via Protocol — no ABC, no framework."""

from __future__ import annotations

from typing import Optional, Protocol
from uuid import UUID

from src.domain.entities.user import User


class UserRepositoryProtocol(Protocol):
    async def get_by_id(self, user_id: UUID) -> Optional[User]: ...

    async def get_by_email(self, email: str) -> Optional[User]: ...

    async def create(self, user: User) -> User: ...
