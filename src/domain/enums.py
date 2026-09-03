"""Domain enumerations. Standard library only.

Every field the ERD types as a bare ``string`` but which is really a fixed set
lives here. Persisted as VARCHAR + CHECK (see ``src.infrastructure.db.types``),
so values stay readable in the database and a typo fails at write time.
"""

from __future__ import annotations

from enum import StrEnum


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
    """How the daily calorie target is derived."""

    AUTO = "auto"  # computed from the profile (Mifflin-St Jeor)
    MANUAL = "manual"  # user sets the number themselves


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
    """Thumbs up / down on an AI-estimated entry."""

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
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class QuestType(StrEnum):
    LOG_FOOD = "log_food"
    LOG_WATER = "log_water"
    LOG_WEIGHT = "log_weight"
    LOG_ACTIVITY = "log_activity"


class CoinReason(StrEnum):
    QUEST_REWARD = "quest_reward"
    STREAK_BONUS = "streak_bonus"
    PURCHASE = "purchase"
    ADJUSTMENT = "adjustment"
