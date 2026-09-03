"""Concrete ``RefreshTokenRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.refresh_token import RefreshToken
from src.infrastructure.db.models.refresh_token_model import RefreshTokenORM


class SQLAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, token: RefreshToken) -> RefreshToken:
        row = RefreshTokenORM.from_domain(token)
        self._session.add(row)
        await self._session.flush()
        return row.to_domain()

    async def get_by_jti(self, jti: UUID) -> RefreshToken | None:
        row = (
            await self._session.execute(
                select(RefreshTokenORM).where(RefreshTokenORM.jti == jti)
            )
        ).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def revoke(self, token: RefreshToken) -> None:
        await self._session.execute(
            update(RefreshTokenORM)
            .where(RefreshTokenORM.jti == token.jti)
            .values(revoked_at=token.revoked_at)
        )
