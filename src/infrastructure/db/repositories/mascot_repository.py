"""Concrete ``MascotRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.mascot import AdminMascotDTO
from src.domain.entities.mascot import Mascot
from src.infrastructure.db.models.mascot_model import MascotImageORM, MascotORM, UserMascotORM
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

    async def list_all(self) -> list[AdminMascotDTO]:
        rows = await self._session.scalars(select(MascotORM).order_by(MascotORM.coin_cost, MascotORM.id))
        owners = dict(
            (await self._session.execute(
                select(UserMascotORM.mascot_id, func.count()).group_by(UserMascotORM.mascot_id)
            )).all()
        )
        equipped = dict(
            (await self._session.execute(
                select(UserORM.equipped_mascot_id, func.count()).group_by(UserORM.equipped_mascot_id)
            )).all()
        )
        return [AdminMascotDTO.from_entity(r.to_domain(), owners.get(r.id, 0), equipped.get(r.id, 0)) for r in rows]

    async def get(self, mascot_id: str) -> Mascot | None:
        row = await self._session.get(MascotORM, mascot_id)
        return row.to_domain() if row else None

    async def usage(self, mascot_id: str) -> tuple[int, int]:
        owners = await self._session.scalar(
            select(func.count()).select_from(UserMascotORM).where(UserMascotORM.mascot_id == mascot_id)
        )
        equipped = await self._session.scalar(
            select(func.count()).select_from(UserORM).where(UserORM.equipped_mascot_id == mascot_id)
        )
        return owners, equipped

    async def add(self, mascot: Mascot) -> None:
        self._session.add(MascotORM.from_domain(mascot))
        await self._session.flush()

    async def update(self, mascot: Mascot) -> None:
        row = await self._session.get(MascotORM, mascot.id)
        row.name, row.coin_cost, row.active = mascot.name, mascot.coin_cost, mascot.active
        row.body_color = mascot.body_color
        stored = {i.state: i for i in row.images}
        for state, image in stored.items():
            if state not in mascot.images:
                row.images.remove(image)  # delete-orphan
        for state, url in mascot.images.items():
            if state in stored:
                stored[state].url = url
            else:
                row.images.append(MascotImageORM(state=state, url=url))
        await self._session.flush()

    async def delete(self, mascot_id: str) -> None:
        await self._session.delete(await self._session.get(MascotORM, mascot_id))
        await self._session.flush()

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
