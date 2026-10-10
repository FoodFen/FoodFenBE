"""HTTP wire models for /admin."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import Field, ValidationInfo, field_validator

from src.adapters.schemas.base import CamelModel
from src.adapters.schemas.restaurant_schemas import DishResponse, RestaurantResponse
from src.application.dtos.admin import (
    AdminQuestDTO,
    AdminQuizQuestionDTO,
    AdminRestaurantDetailDTO,
    AdminRestaurantRowDTO,
    AdminUserListDTO,
    AdminUserRowDTO,
    DashboardDTO,
)
from src.domain.enums import ModerationStatus, QuestCadence, ReviewDecision, SubscriptionTier, UserRole


class ReviewRequest(CamelModel):
    decision: ReviewDecision
    # The updatedAt the reviewer saw; a mismatch is a 409 (the owner edited meanwhile). Absent: no check.
    expected_updated_at: datetime | None = None
    # validate_default so an omitted reason is still checked; the error lands on errors.reason.
    reason: str | None = Field(default=None, max_length=1000, validate_default=True)

    @field_validator("reason")
    @classmethod
    def reason_required_to_reject(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("decision") == ReviewDecision.REJECTED and not (value or "").strip():
            raise ValueError("a reason is required to reject")
        return value


class AdminRestaurantRowResponse(CamelModel):
    id: UUID
    name: str
    status: ModerationStatus
    owner_name: str | None
    owner_email: str
    dish_count: int
    pending_dish_count: int
    updated_at: datetime
    rejection_reason: str | None

    @classmethod
    def from_dto(cls, dto: AdminRestaurantRowDTO) -> AdminRestaurantRowResponse:
        return cls(**vars(dto))


class AdminRestaurantDetailResponse(CamelModel):
    restaurant: RestaurantResponse
    dishes: list[DishResponse]

    @classmethod
    def from_dto(cls, dto: AdminRestaurantDetailDTO) -> AdminRestaurantDetailResponse:
        return cls(
            restaurant=RestaurantResponse.from_dto(dto.restaurant),
            dishes=[DishResponse.from_dto(d) for d in dto.dishes],
        )


class _DashboardCounts(CamelModel):
    premium_revenue: int
    ad_revenue: int
    new_users: int
    new_restaurants: int
    food_entries: int


class DashboardTotalsResponse(_DashboardCounts):
    premium_users: int


class DashboardDayResponse(_DashboardCounts):
    date: date


class DashboardResponse(CamelModel):
    # "from" is a Python keyword: declare it as from_date with an explicit alias.
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    totals: DashboardTotalsResponse
    daily: list[DashboardDayResponse]

    @classmethod
    def from_dto(cls, dto: DashboardDTO) -> DashboardResponse:
        return cls(
            from_date=dto.from_date,
            to_date=dto.to_date,
            totals=DashboardTotalsResponse(
                premium_revenue=dto.premium_revenue, ad_revenue=dto.ad_revenue,
                new_users=dto.new_users, new_restaurants=dto.new_restaurants,
                food_entries=dto.food_entries, premium_users=dto.premium_users,
            ),
            daily=[DashboardDayResponse(**vars(d)) for d in dto.daily],
        )


class AdminUserRowResponse(CamelModel):
    id: int
    display_name: str | None
    email: str
    role: UserRole
    tier: SubscriptionTier
    streak: int
    created_at: datetime
    is_active: bool


class AdminUserListResponse(CamelModel):
    users: list[AdminUserRowResponse]
    total: int
    next_cursor: str | None

    @classmethod
    def from_dto(cls, dto: AdminUserListDTO) -> AdminUserListResponse:
        return cls(
            users=[AdminUserRowResponse(**vars(u)) for u in dto.users],
            total=dto.total,
            next_cursor=dto.next_cursor,
        )


class AdminQuizQuestionResponse(CamelModel):
    id: UUID
    question: str
    topic: str
    active: bool

    @classmethod
    def from_dto(cls, dto: AdminQuizQuestionDTO) -> AdminQuizQuestionResponse:
        return cls(**vars(dto))


class AdminQuestResponse(CamelModel):
    id: UUID
    title: str
    target: int
    reward_coins: int
    cadence: QuestCadence
    active: bool

    @classmethod
    def from_dto(cls, dto: AdminQuestDTO) -> AdminQuestResponse:
        return cls(**vars(dto))
