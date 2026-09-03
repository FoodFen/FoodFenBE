"""ORM model for tracked refresh tokens."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.refresh_token import RefreshToken
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey


class RefreshTokenORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "refresh_tokens"

    jti: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_domain(self) -> RefreshToken:
        return RefreshToken(
            id=self.id,
            user_id=self.user_id,
            jti=self.jti,
            expires_at=self.expires_at,
            created_at=self.created_at,
            revoked_at=self.revoked_at,
        )

    @staticmethod
    def from_domain(token: RefreshToken) -> RefreshTokenORM:
        return RefreshTokenORM(
            id=token.id,
            user_id=token.user_id,
            jti=token.jti,
            expires_at=token.expires_at,
            created_at=token.created_at,
            revoked_at=token.revoked_at,
        )
