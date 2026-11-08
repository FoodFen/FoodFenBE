"""Concrete ``NutritionTipRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.nutrition_tip import NutritionTip
from src.infrastructure.db.models.nutrition_tip_model import NutritionTipORM


class SQLAlchemyNutritionTipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, active_only: bool) -> list[NutritionTip]:
        stmt = select(NutritionTipORM).order_by(NutritionTipORM.created_at.desc(), NutritionTipORM.id)
        if active_only:
            stmt = stmt.where(NutritionTipORM.is_active.is_(True))
        return [row.to_domain() for row in await self._session.scalars(stmt)]

    async def get(self, tip_id: UUID) -> NutritionTip | None:
        row = await self._session.get(NutritionTipORM, tip_id)
        return row.to_domain() if row else None

    async def add(self, tip: NutritionTip) -> None:
        self._session.add(NutritionTipORM.from_domain(tip))
        await self._session.flush()

    async def update(self, tip: NutritionTip) -> None:
        await self._session.merge(NutritionTipORM.from_domain(tip))
        await self._session.flush()

    async def delete(self, tip_id: UUID) -> None:
        await self._session.delete(await self._session.get(NutritionTipORM, tip_id))
        await self._session.flush()
