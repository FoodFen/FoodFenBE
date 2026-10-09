"""Admin read models. Frozen dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.application.dtos.restaurant import DishOutputDTO, RestaurantOutputDTO
from src.domain.enums import ModerationStatus


@dataclass(frozen=True)
class AdminRestaurantRowDTO:
    id: UUID
    name: str
    status: ModerationStatus
    owner_name: str | None
    owner_email: str
    dish_count: int
    pending_dish_count: int
    updated_at: datetime
    rejection_reason: str | None


@dataclass(frozen=True)
class AdminRestaurantDetailDTO:
    restaurant: RestaurantOutputDTO
    dishes: list[DishOutputDTO]


@dataclass(frozen=True)
class DashboardDayDTO:
    date: date
    premium_revenue: int
    ad_revenue: int
    new_users: int
    new_restaurants: int


@dataclass(frozen=True)
class DashboardDTO:
    from_date: date
    to_date: date
    premium_revenue: int
    ad_revenue: int
    new_users: int
    new_restaurants: int
    daily: list[DashboardDayDTO]
