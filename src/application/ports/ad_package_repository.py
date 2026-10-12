"""Persistence port for ad packages."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from src.domain.entities.ad_package import AdPackage


class AdPackageRepositoryProtocol(Protocol):
    async def add(self, package: AdPackage) -> None: ...

    async def get(self, package_id: UUID) -> AdPackage | None: ...

    async def update(self, package: AdPackage) -> None: ...

    async def list_packages(self, active_only: bool) -> list[AdPackage]:
        """Fewest days first."""
        ...
