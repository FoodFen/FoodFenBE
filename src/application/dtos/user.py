"""Plain-Python DTOs crossing the application boundary. Standard library only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.entities.user import User


@dataclass(frozen=True)
class CreateUserInputDTO:
    email: str
    name: str


@dataclass(frozen=True)
class UserOutputDTO:
    id: UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime

    @classmethod
    def from_entity(cls, user: User) -> UserOutputDTO:
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            created_at=user.created_at,
        )
