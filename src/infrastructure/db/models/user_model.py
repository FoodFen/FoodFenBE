"""SQLAlchemy ORM model for users — a separate class from the domain entity.

Mapping between the two is explicit: ``to_domain`` / ``from_domain``.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.user import User
from src.infrastructure.db.base import Base


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_domain(self) -> User:
        return User(
            id=self.id,
            email=self.email,
            name=self.name,
            is_active=self.is_active,
            created_at=self.created_at,
        )

    @staticmethod
    def from_domain(user: User) -> "UserORM":
        return UserORM(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            created_at=user.created_at,
        )
