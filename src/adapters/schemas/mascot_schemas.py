"""HTTP wire models for mascots."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from src.adapters.schemas.base import CamelModel
from src.adapters.schemas.image_schemas import CloudinaryImageUrl
from src.application.dtos.mascot import AdminMascotDTO, MascotsOutputDTO
from src.domain.enums import MascotState


class MascotResponse(CamelModel):
    id: str
    name: str
    coin_cost: int
    owned: bool
    images: dict[MascotState, str]  # only states that have one; the app falls back to `idle`


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


# --- admin ---

# The entity enforces these (and trims the name); repeating them here turns most bad input into a plain 422.
_ArtUrl = Annotated[CloudinaryImageUrl, Field(max_length=2048)]


class AdminMascotResponse(CamelModel):
    id: str
    name: str
    coin_cost: int
    active: bool
    images: dict[MascotState, str]
    owner_count: int
    equipped_count: int

    @classmethod
    def from_dto(cls, dto: AdminMascotDTO) -> AdminMascotResponse:
        return cls(**vars(dto))


class CreateMascotRequest(CamelModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,32}$")
    name: str = Field(min_length=1, max_length=40)
    coin_cost: int = Field(ge=0, le=1_000_000)
    active: bool = False  # a draft until the admin has finished the art
    images: dict[MascotState, _ArtUrl] = {}


class UpdateMascotRequest(CamelModel):
    """Partial: an absent (or null) field is left as is. ``images`` merges per state; ``null`` removes a state."""

    name: str | None = Field(default=None, min_length=1, max_length=40)
    coin_cost: int | None = Field(default=None, ge=0, le=1_000_000)
    active: bool | None = None
    images: dict[MascotState, _ArtUrl | None] | None = None
