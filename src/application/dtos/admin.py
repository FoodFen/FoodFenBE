"""Admin read models. Frozen dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from src.application.dtos.quiz import QuizOptionDTO
from src.application.dtos.restaurant import DishOutputDTO, RestaurantOutputDTO
from src.domain.entities.quiz import QuizQuestion
from src.domain.enums import (
    ModerationStatus,
    PaymentProvider,
    PaymentStatus,
    PlanType,
    QuestCadence,
    SubscriptionTier,
    UserRole,
)


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
class AdminRestaurantListDTO:
    restaurants: list[AdminRestaurantRowDTO]
    total: int
    next_cursor: str | None


@dataclass(frozen=True)
class AdminRestaurantDetailDTO:
    restaurant: RestaurantOutputDTO
    dishes: list[DishOutputDTO]
    owner_name: str | None
    owner_email: str


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
    question: str  # the question text
    topic: str  # the topic's label
    topic_id: UUID
    options: list[QuizOptionDTO]
    correct_option_id: str
    explanation: str
    active: bool

    @classmethod
    def from_entity(cls, q: QuizQuestion, topic_label: str) -> AdminQuizQuestionDTO:
        return cls(
            id=q.id, question=q.text, topic=topic_label, topic_id=q.topic_id,
            options=[QuizOptionDTO(o.id, o.text) for o in q.options],
            correct_option_id=q.correct_option_id, explanation=q.explanation, active=q.active,
        )


@dataclass(frozen=True)
class AdminQuizTopicDTO:
    id: UUID
    slug: str
    label: str
    active: bool
    active_question_count: int


@dataclass(frozen=True)
class AdminQuestDTO:
    id: UUID
    title: str
    target: int
    reward_coins: int
    cadence: QuestCadence
    active: bool


@dataclass(frozen=True)
class AdminPaymentFilterDTO:
    """All optional. ``start`` inclusive, ``end`` exclusive (Vietnam-day bounds as UTC instants)."""

    q: str | None = None
    status: PaymentStatus | None = None
    plan_type: PlanType | None = None
    provider: PaymentProvider | None = None
    start: datetime | None = None
    end: datetime | None = None


@dataclass(frozen=True)
class AdminPaymentRowDTO:
    id: UUID
    order_code: int
    user_id: int
    user_email: str
    user_name: str | None
    restaurant_id: UUID | None  # the payer's restaurant, only for ad_package payments
    restaurant_name: str | None
    plan_type: PlanType
    provider: PaymentProvider
    amount: Decimal
    status: PaymentStatus
    ad_days: int | None
    created_at: datetime
    paid_at: datetime | None


@dataclass(frozen=True)
class AdminPaymentListDTO:
    payments: list[AdminPaymentRowDTO]
    total: int
    next_cursor: str | None
