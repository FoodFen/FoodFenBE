"""Concrete ``AdPackageRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.ad_package import AdPackage
from src.infrastructure.db.models.ad_package_model import AdPackageORM


class SQLAlchemyAdPackageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, package: AdPackage) -> None:
        self._session.add(AdPackageORM.from_domain(package))
        await self._session.flush()

    async def get(self, package_id: UUID) -> AdPackage | None:
        row = await self._session.get(AdPackageORM, package_id)
        return row.to_domain() if row else None

    async def update(self, package: AdPackage) -> None:
        await self._session.merge(AdPackageORM.from_domain(package))
        await self._session.flush()

    async def list_packages(self, active_only: bool) -> list[AdPackage]:
        stmt = select(AdPackageORM).order_by(AdPackageORM.days, AdPackageORM.created_at)
        if active_only:
            stmt = stmt.where(AdPackageORM.active.is_(True))
        return [row.to_domain() for row in (await self._session.execute(stmt)).scalars()]
