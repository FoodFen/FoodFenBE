"""Use cases: admin list / create / edit ad packages (no delete: payments snapshot them)."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.ad import AdPackageDTO
from src.application.ports.ad_package_repository import AdPackageRepositoryProtocol
from src.domain.entities.ad_package import AdPackage
from src.domain.exceptions import AdPackageNotFoundException


@dataclass
class ListAdPackagesUseCase:
    packages: AdPackageRepositoryProtocol

    async def execute(self) -> list[AdPackageDTO]:
        """Every package, inactive ones included."""
        return [AdPackageDTO.from_entity(p) for p in await self.packages.list_packages(active_only=False)]


@dataclass
class CreateAdPackageUseCase:
    packages: AdPackageRepositoryProtocol

    async def execute(self, days: int, price_vnd: int, active: bool) -> AdPackageDTO:
        package = AdPackage.create(days, price_vnd, active)
        await self.packages.add(package)
        return AdPackageDTO.from_entity(package)


@dataclass
class UpdateAdPackageUseCase:
    packages: AdPackageRepositoryProtocol

    async def execute(
        self, package_id: UUID, days: int | None, price_vnd: int | None, active: bool | None
    ) -> AdPackageDTO:
        package = await self.packages.get(package_id)
        if package is None:
            raise AdPackageNotFoundException(f"ad package {package_id} not found")
        package.update(days, price_vnd, active)
        await self.packages.update(package)
        return AdPackageDTO.from_entity(package)
