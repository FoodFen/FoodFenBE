"""Use cases: admin list / create / edit / delete mascots. Rules live in the ``Mascot`` entity."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.mascot import AdminMascotDTO
from src.application.ports.mascot_repository import MascotRepositoryProtocol
from src.domain.entities.mascot import Mascot
from src.domain.enums import MascotState
from src.domain.exceptions import MascotIdTakenException, MascotInUseException, MascotNotFoundException


@dataclass
class ListAdminMascotsUseCase:
    mascots: MascotRepositoryProtocol

    async def execute(self) -> list[AdminMascotDTO]:
        return await self.mascots.list_all()


@dataclass
class CreateMascotUseCase:
    mascots: MascotRepositoryProtocol

    async def execute(
        self, mascot_id: str, name: str, coin_cost: int, active: bool, images: dict[MascotState, str]
    ) -> AdminMascotDTO:
        if await self.mascots.get(mascot_id) is not None:
            raise MascotIdTakenException(f"mascot {mascot_id!r} already exists")
        mascot = Mascot.create(mascot_id, name, coin_cost, active, images)
        await self.mascots.add(mascot)
        return AdminMascotDTO.from_entity(mascot, 0, 0)


@dataclass
class UpdateMascotUseCase:
    mascots: MascotRepositoryProtocol

    async def execute(
        self,
        mascot_id: str,
        name: str | None,
        coin_cost: int | None,
        active: bool | None,
        images: dict[MascotState, str | None] | None,
    ) -> AdminMascotDTO:
        mascot = await self.mascots.get(mascot_id)
        if mascot is None:
            raise MascotNotFoundException(f"no mascot {mascot_id!r}")
        mascot.update(name, coin_cost, active, images)
        await self.mascots.update(mascot)
        return AdminMascotDTO.from_entity(mascot, *await self.mascots.usage(mascot_id))


@dataclass
class DeleteMascotUseCase:
    mascots: MascotRepositoryProtocol

    async def execute(self, mascot_id: str) -> None:
        mascot = await self.mascots.get(mascot_id)
        if mascot is None:
            raise MascotNotFoundException(f"no mascot {mascot_id!r}")
        mascot.ensure_deletable()
        owners, equipped = await self.mascots.usage(mascot_id)
        if owners or equipped:
            raise MascotInUseException(
                f"{owners} users own it and {equipped} have it equipped; hide it instead of deleting"
            )
        await self.mascots.delete(mascot_id)
