"""Concrete ``FoodChangeRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.food_change import FoodChange
from src.infrastructure.db.models.food_change_model import FoodChangeORM
from src.infrastructure.db.models.user_model import UserORM


class SQLAlchemyFoodChangeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, change: FoodChange) -> None:
        self._session.add(FoodChangeORM.from_domain(change))
        await self._session.flush()

    async def list_for_food(self, food_id: UUID) -> list[tuple[FoodChange, str | None]]:
        rows = await self._session.execute(
            select(FoodChangeORM, UserORM.email)
            .outerjoin(UserORM, UserORM.id == FoodChangeORM.admin_id)
            .where(FoodChangeORM.food_id == food_id)
            .order_by(FoodChangeORM.created_at.desc(), FoodChangeORM.id.desc())
        )
        return [(row.to_domain(), email) for row, email in rows]
