"""Concrete ``SocialIdentityRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.social_identity import SocialIdentity
from src.domain.enums import AuthProvider
from src.infrastructure.db.models.social_identity_model import SocialIdentityORM


class SQLAlchemySocialIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_provider_subject(
        self, provider: AuthProvider, provider_user_id: str
    ) -> SocialIdentity | None:
        row = (
            await self._session.execute(
                select(SocialIdentityORM).where(
                    SocialIdentityORM.provider == provider,
                    SocialIdentityORM.provider_user_id == provider_user_id,
                )
            )
        ).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def create(self, identity: SocialIdentity) -> SocialIdentity:
        row = SocialIdentityORM.from_domain(identity)
        self._session.add(row)
        await self._session.flush()
        return row.to_domain()
