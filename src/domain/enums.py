"""Domain enumerations. Standard library only.

Every field the ERD types as a bare ``string`` but which is really a fixed set
lives here. Persisted as VARCHAR + CHECK (see ``src.infrastructure.db.types``),
so values stay readable in the database and a typo fails at write time.
"""

from __future__ import annotations

from enum import StrEnum


class AuthProvider(StrEnum):
    GOOGLE = "google"
    APPLE = "apple"


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class UnitSystem(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class ActivityLevel(StrEnum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    ACTIVE = "active"
    VERY_ACTIVE = "very_active"


class DietType(StrEnum):
    BALANCED = "balanced"
    KETO = "keto"
    LOW_CARB = "low_carb"
    HIGH_PROTEIN = "high_protein"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"


class CalorieCalcMode(StrEnum):
    AUTO = "auto"  # from the profile, via Mifflin-St Jeor
    MANUAL = "manual"


class CalorieLeftMode(StrEnum):
    SMART = "smart"
    ALL_CALORIES = "all_calories"


class SubscriptionTier(StrEnum):
    """Feature gate. Fiber tracking and custom ingredients are PREMIUM-only."""

    FREE = "free"
    PREMIUM = "premium"


class InputMethod(StrEnum):
    VOICE = "voice"
    IMAGE = "image"
    TYPE = "type"
    MANUAL = "manual"


class AiFeedback(StrEnum):
    UP = "up"
    DOWN = "down"


class ActivitySource(StrEnum):
    MANUAL = "manual"
    APPLE_HEALTH = "apple_health"
    GOOGLE_FIT = "google_fit"


class PlanType(StrEnum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    CANCELED = "canceled"
    EXPIRED = "expired"
    TRIAL = "trial"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


class QuestType(StrEnum):
    """Matches the quest catalog in FoodFenFE/src/db/schema.ts."""

    LOG_BREAKFAST = "log_breakfast"
    LOG_ALL_MEALS = "log_all_meals"
    HIT_CALORIE_GOAL = "hit_calorie_goal"
    HIT_PROTEIN_GOAL = "hit_protein_goal"
    DRINK_WATER = "drink_water"
    LOG_WEIGHT = "log_weight"
    STAY_ACTIVE_WEEK = "stay_active_week"


class QuestCadence(StrEnum):
    """`daily` quests are issued fresh each day; `weekly` once per calendar week."""

    DAILY = "daily"
    WEEKLY = "weekly"


class CoinReason(StrEnum):
    QUEST_COMPLETED = "quest_completed"
    STREAK_BONUS = "streak_bonus"
    PURCHASE = "purchase"
    SPEND = "spend"
    ADJUSTMENT = "adjustment"
