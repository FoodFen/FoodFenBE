"""Entity invariants and ORM<->domain round-trips. No DB, no FastAPI.

The round-trip tests build ORM instances in memory (never persisted), so they
catch a field dropped from ``to_domain`` / ``from_domain`` without needing
Postgres.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from src.domain.entities.activity_log import ActivityLog
from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.entities.daily_goal import DailyGoal
from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.ingredient import Ingredient
from src.domain.entities.quest import Quest
from src.domain.entities.streak import Streak
from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User
from src.domain.entities.water_log import WaterLog
from src.domain.entities.weight_log import WeightLog
from src.domain.enums import (
    ActivitySource,
    CalorieLeftMode,
    CoinReason,
    Gender,
    InputMethod,
    PlanType,
    QuestType,
    SubscriptionStatus,
    SubscriptionTier,
)
from src.domain.exceptions import InvalidAttributeException, InvalidUserAttributeException
from src.infrastructure.db.models.activity_log_model import ActivityLogORM
from src.infrastructure.db.models.coin_transaction_model import CoinTransactionORM
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM
from src.infrastructure.db.models.food_entry_model import FoodEntryORM
from src.infrastructure.db.models.quest_model import QuestORM
from src.infrastructure.db.models.streak_model import StreakORM
from src.infrastructure.db.models.subscription_model import SubscriptionORM
from src.infrastructure.db.models.user_model import UserORM
from src.infrastructure.db.models.water_log_model import WaterLogORM
from src.infrastructure.db.models.weight_log_model import WeightLogORM

USER_ID = 1  # user_id FKs are int now; only Ingredient/RefreshToken.jti etc. stay UUID
TODAY = date(2026, 9, 3)


def _full_user() -> User:
    user = User.create(email="round@trip.com", name="Round Trip")
    user.gender = Gender.FEMALE
    user.birth_year = 1998
    user.height = 165.0
    user.weight_current = 60.5
    user.weight_goal = 55.0
    user.subscription_tier = SubscriptionTier.PREMIUM
    user.password_hash = "argon2$fake"
    user.calorie_left_mode = CalorieLeftMode.SMART
    user.weekly_rate_kg = 0.5
    user.verify_email(datetime(2026, 9, 1, tzinfo=UTC))
    return user


def _food_entry() -> FoodEntry:
    entry = FoodEntry.create(
        user_id=USER_ID,
        name="Post-workout lunch",
        input_method=InputMethod.IMAGE,
        total_kcal=520,
        carbs_g=45.0,
        protein_g=30.0,
        fat_g=22.5,
        image_url="https://cdn.example/meal.jpg",
        fiber_g=6.0,
    )
    entry.ingredients = [
        Ingredient.create(entry.id, "chicken breast", 150.0, 250, 0.0, 46.0, 5.4, fiber_g=0.0),
        Ingredient.create(entry.id, "brown rice", 120.0, 140, 30.0, 3.0, 1.1),
    ]
    return entry


# --- round-trips ---------------------------------------------------------------

ROUND_TRIPS = [
    (_full_user(), UserORM),
    (_food_entry(), FoodEntryORM),
    (
        DailyGoal.create(USER_ID, 2000, 200.0, 150.0, 60.0, 2500, TODAY),
        DailyGoalORM,
    ),
    (ActivityLog.create(USER_ID, "running", 320, ActivitySource.APPLE_HEALTH), ActivityLogORM),
    (WeightLog.create(USER_ID, 60.4, TODAY), WeightLogORM),
    (WaterLog.create(USER_ID, 350), WaterLogORM),
    (Streak(id=uuid4(), user_id=USER_ID, current_streak=4, longest_streak=9), StreakORM),
    (Quest.create(USER_ID, QuestType.DRINK_WATER, 8, 25, TODAY), QuestORM),
    (CoinTransaction.create(USER_ID, -50, CoinReason.PURCHASE), CoinTransactionORM),
    (
        Subscription.create(
            USER_ID, PlanType.ANNUAL, TODAY, TODAY + timedelta(days=365), Decimal("59.99")
        ),
        SubscriptionORM,
    ),
]


@pytest.mark.parametrize(
    ("entity", "orm_cls"), ROUND_TRIPS, ids=lambda v: getattr(v, "__name__", type(v).__name__)
)
def test_orm_round_trip_preserves_entity(entity, orm_cls):
    assert orm_cls.from_domain(entity).to_domain() == entity


def test_food_entry_round_trip_keeps_ingredients():
    entry = _food_entry()
    restored = FoodEntryORM.from_domain(entry).to_domain()
    assert [i.name for i in restored.ingredients] == ["chicken breast", "brown rice"]
    assert restored.ingredients == entry.ingredients


# --- invariants ----------------------------------------------------------------


def test_user_rejects_implausible_birth_year():
    with pytest.raises(InvalidUserAttributeException):
        User(email="a@b.co", name="A", birth_year=1723)


def test_user_rejects_non_positive_height():
    with pytest.raises(InvalidUserAttributeException):
        User(email="a@b.co", name="A", height=0.0)


def test_ingredient_rejects_negative_macros():
    with pytest.raises(InvalidAttributeException):
        Ingredient.create(uuid4(), "salt", 1.0, 0, -1.0, 0.0, 0.0)


def test_food_entry_rejects_blank_name():
    with pytest.raises(InvalidAttributeException):
        FoodEntry.create(
            user_id=USER_ID,
            name="   ",
            input_method=InputMethod.MANUAL,
            total_kcal=100,
            carbs_g=10.0,
            protein_g=5.0,
            fat_g=2.0,
        )


def test_quest_rejects_completion_ratio_out_of_range():
    with pytest.raises(InvalidAttributeException):
        Quest.create(USER_ID, QuestType.DRINK_WATER, 8, 25, completion_ratio=1.5)


def test_water_log_rejects_zero_amount():
    with pytest.raises(InvalidAttributeException):
        WaterLog.create(USER_ID, 0)


def test_streak_longest_cannot_trail_current():
    with pytest.raises(InvalidAttributeException):
        Streak(id=uuid4(), user_id=USER_ID, current_streak=10, longest_streak=3)


def test_coin_transaction_rejects_zero_amount():
    with pytest.raises(InvalidAttributeException):
        CoinTransaction.create(USER_ID, 0, CoinReason.ADJUSTMENT)


def test_subscription_rejects_end_before_start():
    with pytest.raises(InvalidAttributeException):
        Subscription.create(
            USER_ID, PlanType.MONTHLY, TODAY, TODAY - timedelta(days=1), Decimal("9.99")
        )


def test_subscription_price_stays_exact():
    sub = Subscription.create(
        USER_ID, PlanType.MONTHLY, TODAY, TODAY + timedelta(days=30), "9.99"
    )
    assert sub.price == Decimal("9.99")
    assert sub.price * 3 == Decimal("29.97")  # a float would give 29.970000000000002


def test_subscription_covers_only_inside_active_window():
    sub = Subscription.create(
        USER_ID, PlanType.MONTHLY, TODAY, TODAY + timedelta(days=30), Decimal("9.99")
    )
    assert sub.covers(TODAY)
    assert not sub.covers(TODAY - timedelta(days=1))

    sub.status = SubscriptionStatus.CANCELED
    assert not sub.covers(TODAY)


def test_subscription_with_no_end_date_covers_indefinitely():
    sub = Subscription.create(USER_ID, PlanType.MONTHLY, TODAY, None, Decimal("9.99"))
    assert sub.covers(TODAY + timedelta(days=365))
    assert not sub.covers(TODAY - timedelta(days=1))


def test_quest_is_achieved_at_target():
    quest = Quest.create(USER_ID, QuestType.LOG_BREAKFAST, target=3, reward_coins=10)
    assert not quest.is_achieved
    quest.progress = 3
    assert quest.is_achieved


def test_user_allows_missing_display_name():
    user = User(email="a@b.co", name=None)
    assert user.name is None


def test_user_blank_name_collapses_to_none():
    user = User(email="a@b.co", name="   ")
    assert user.name is None


def test_user_rejects_negative_weekly_rate():
    with pytest.raises(InvalidUserAttributeException):
        User(email="a@b.co", name="A", weekly_rate_kg=-0.5)
