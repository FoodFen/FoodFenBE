"""Restaurant / dish DTOs: frozen dataclasses, never Pydantic or ORM."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.enums import ModerationStatus


@dataclass(frozen=True)
class RestaurantOutputDTO:
    id: UUID
    name: str
    description: str | None
    address: str
    phone: str
    opening_hours: str
    latitude: float
    longitude: float
    image_url: str | None
    status: ModerationStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_entity(cls, r: Restaurant) -> RestaurantOutputDTO:
        return cls(
            id=r.id, name=r.name, description=r.description, address=r.address, phone=r.phone,
            opening_hours=r.opening_hours, latitude=r.latitude, longitude=r.longitude,
            image_url=r.image_url, status=r.status, rejection_reason=r.rejection_reason,
            created_at=r.created_at, updated_at=r.updated_at, reviewed_at=r.reviewed_at,
        )


@dataclass(frozen=True)
class DishOutputDTO:
    id: UUID
    restaurant_id: UUID
    name: str
    description: str | None
    image_url: str | None
    price: Decimal
    serving_g: int
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None
    status: ModerationStatus
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    reviewed_at: datetime | None

    @classmethod
    def from_entity(cls, d: Dish) -> DishOutputDTO:
        return cls(
            id=d.id, restaurant_id=d.restaurant_id, name=d.name, description=d.description,
            image_url=d.image_url, price=d.price, serving_g=d.serving_g, kcal=d.kcal,
            protein_g=d.protein_g, carbs_g=d.carbs_g, fat_g=d.fat_g, fiber_g=d.fiber_g,
            status=d.status, rejection_reason=d.rejection_reason, created_at=d.created_at,
            updated_at=d.updated_at, reviewed_at=d.reviewed_at,
        )


@dataclass(frozen=True)
class CreateRestaurantInputDTO:
    user_id: int
    name: str
    address: str
    phone: str
    opening_hours: str
    latitude: float
    longitude: float
    description: str | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class UpdateRestaurantInputDTO:
    user_id: int
    updates: dict[str, Any]  # only the fields the client sent (exclude_unset)


@dataclass(frozen=True)
class CreateDishInputDTO:
    user_id: int
    name: str
    price: Decimal
    serving_g: int
    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float
    fiber_g: float | None = None
    description: str | None = None
    image_url: str | None = None


@dataclass(frozen=True)
class UpdateDishInputDTO:
    user_id: int
    dish_id: UUID
    updates: dict[str, Any]
