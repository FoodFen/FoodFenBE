"""Concrete ``MascotRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.mascot import Mascot
from src.infrastructure.db.models.mascot_model import MascotORM, UserMascotORM
from src.infrastructure.db.models.user_model import UserORM


class SQLAlchemyMascotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[Mascot]:
        rows = await self._session.scalars(
            select(MascotORM).where(MascotORM.active.is_(True)).order_by(MascotORM.coin_cost, MascotORM.id)
        )
        return [row.to_domain() for row in rows]

    async def get_active(self, mascot_id: str) -> Mascot | None:
        row = await self._session.scalar(
            select(MascotORM).where(MascotORM.id == mascot_id, MascotORM.active.is_(True))
        )
        return row.to_domain() if row else None

    async def owned_ids(self, user_id: int) -> set[str]:
        rows = await self._session.scalars(
            select(UserMascotORM.mascot_id).where(UserMascotORM.user_id == user_id)
        )
        return set(rows)

    async def add_owned(self, user_id: int, mascot_id: str) -> None:
        self._session.add(UserMascotORM(user_id=user_id, mascot_id=mascot_id))
        await self._session.flush()

    async def get_equipped(self, user_id: int) -> str:
        return await self._session.scalar(
            select(UserORM.equipped_mascot_id).where(UserORM.id == user_id)
        )

    async def set_equipped(self, user_id: int, mascot_id: str) -> None:
        await self._session.execute(
            update(UserORM).where(UserORM.id == user_id).values(equipped_mascot_id=mascot_id)
        )
