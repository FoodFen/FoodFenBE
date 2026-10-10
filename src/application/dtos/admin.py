"""Admin read models. Frozen dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from src.application.dtos.restaurant import DishOutputDTO, RestaurantOutputDTO
from src.domain.enums import ModerationStatus, QuestCadence, SubscriptionTier, UserRole


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
    food_entries: int


@dataclass(frozen=True)
class DashboardDTO:
    from_date: date
    to_date: date
    premium_revenue: int
    ad_revenue: int
    new_users: int
    new_restaurants: int
    food_entries: int
    premium_users: int  # current count, not per day: there is no history of tier
    daily: list[DashboardDayDTO]


@dataclass(frozen=True)
class AdminUserRowDTO:
    id: int
    display_name: str | None
    email: str
    role: UserRole
    tier: SubscriptionTier
    streak: int
    created_at: datetime
    is_active: bool


@dataclass(frozen=True)
class AdminUserListDTO:
    users: list[AdminUserRowDTO]
    total: int
    next_cursor: str | None


@dataclass(frozen=True)
class AdminQuizQuestionDTO:
    id: UUID
    question: str
    topic: str
    active: bool


@dataclass(frozen=True)
class AdminQuestDTO:
    id: UUID
    title: str
    target: int
    reward_coins: int
    cadence: QuestCadence
    active: bool
