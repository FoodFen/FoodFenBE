"""Concrete ``FoodCatalogRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.catalog_food import CatalogFood
from src.infrastructure.db.models.food_model import FoodORM


class SQLAlchemyFoodCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[CatalogFood]:
        rows = await self._session.scalars(select(FoodORM).where(FoodORM.archived.is_(False)).order_by(FoodORM.slug))
        return [row.to_domain() for row in rows]

    async def get_by_slug(self, slug: str) -> CatalogFood | None:
        row = await self._session.scalar(select(FoodORM).where(FoodORM.slug == slug))
        return row.to_domain() if row else None

    async def list_all(self) -> list[CatalogFood]:
        return [row.to_domain() for row in await self._session.scalars(select(FoodORM))]

    async def list_changed(self, since: datetime | None) -> list[CatalogFood]:
        query = select(FoodORM).order_by(FoodORM.slug)
        if since is not None:
            query = query.where(FoodORM.updated_at >= since)
        return [row.to_domain() for row in await self._session.scalars(query)]

    async def add(self, food: CatalogFood) -> None:
        self._session.add(FoodORM.from_domain(food))
        await self._session.flush()

    async def update(self, food: CatalogFood) -> None:
        row = await self._session.get(FoodORM, food.id)
        row.apply(food)
        await self._session.flush()
