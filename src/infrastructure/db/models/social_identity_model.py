"""ORM model linking a (provider, provider_user_id) pair to a user."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.social_identity import SocialIdentity
from src.domain.enums import AuthProvider
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class SocialIdentityORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "social_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_social_identities_provider_sub"),
    )

    provider: Mapped[AuthProvider] = mapped_column(
        enum_column(AuthProvider, "auth_provider"), nullable=False
    )
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_domain(self) -> SocialIdentity:
        return SocialIdentity(
            id=self.id,
            user_id=self.user_id,
            provider=self.provider,
            provider_user_id=self.provider_user_id,
            created_at=self.created_at,
        )

    @staticmethod
    def from_domain(identity: SocialIdentity) -> SocialIdentityORM:
        return SocialIdentityORM(
            id=identity.id,
            user_id=identity.user_id,
            provider=identity.provider,
            provider_user_id=identity.provider_user_id,
            created_at=identity.created_at,
        )
