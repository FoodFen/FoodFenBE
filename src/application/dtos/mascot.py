"""Mascot DTOs — frozen dataclasses, never Pydantic models or ORM rows."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.mascot import Mascot
from src.domain.enums import MascotState


@dataclass(frozen=True)
class MascotOutputDTO:
    id: str
    name: str
    coin_cost: int
    owned: bool
    images: dict[MascotState, str]  # only the states that have one


@dataclass(frozen=True)
class MascotsOutputDTO:
    balance: int
    equipped_id: str
    mascots: list[MascotOutputDTO]


@dataclass(frozen=True)
class AdminMascotDTO:
    id: str
    name: str
    coin_cost: int
    active: bool
    images: dict[MascotState, str]
    owner_count: int  # user_mascots rows
    equipped_count: int  # users with it equipped

    @classmethod
    def from_entity(cls, m: Mascot, owner_count: int, equipped_count: int) -> AdminMascotDTO:
        return cls(m.id, m.name, m.coin_cost, m.active, dict(m.images), owner_count, equipped_count)
