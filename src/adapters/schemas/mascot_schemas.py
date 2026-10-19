"""HTTP wire models for mascots."""

from __future__ import annotations

from src.adapters.schemas.base import CamelModel
from src.application.dtos.mascot import MascotsOutputDTO


class MascotResponse(CamelModel):
    id: str
    name: str
    coin_cost: int
    owned: bool


class MascotsResponse(CamelModel):
    balance: int
    equipped_id: str
    mascots: list[MascotResponse]

    @classmethod
    def from_dto(cls, dto: MascotsOutputDTO) -> MascotsResponse:
        return cls(
            balance=dto.balance,
            equipped_id=dto.equipped_id,
            mascots=[MascotResponse(**vars(m)) for m in dto.mascots],
        )


class EquipMascotRequest(CamelModel):
    mascot_id: str


class EquipMascotResponse(CamelModel):
    equipped_id: str
