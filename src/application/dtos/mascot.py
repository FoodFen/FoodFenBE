"""Mascot DTOs — frozen dataclasses, never Pydantic models or ORM rows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MascotOutputDTO:
    id: str
    name: str
    coin_cost: int
    owned: bool


@dataclass(frozen=True)
class MascotsOutputDTO:
    balance: int
    equipped_id: str
    mascots: list[MascotOutputDTO]
