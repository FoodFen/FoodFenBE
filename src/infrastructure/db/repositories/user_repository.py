"""Concrete ``UserRepositoryProtocol`` implementation backed by async SQLAlchemy."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User
from src.infrastructure.db.models.user_model import UserORM


class SQLAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserORM, user_id)
        return row.to_domain() if row is not None else None

    async def get_by_email(self, email: str) -> User | None:
        row = (
            await self._session.execute(select(UserORM).where(UserORM.email == email))
        ).scalar_one_or_none()
        return row.to_domain() if row is not None else None

    async def create(self, user: User) -> User:
        row = UserORM.from_domain(user)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return row.to_domain()
