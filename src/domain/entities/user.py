"""User entity. Standard library only — invariants enforced on construction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from src.domain.enums import (
    ActivityLevel,
    CalorieCalcMode,
    CalorieLeftMode,
    DietType,
    Gender,
    SubscriptionTier,
    UnitSystem,
)
from src.domain.exceptions import InvalidUserAttributeException, WeakPasswordException
from src.domain.validation import require_non_negative, require_positive

# Deliberately permissive: "something@something.something", no whitespace.
# ponytail: naive regex, swap for a real RFC 5322 validator only if bad addresses reach production.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_EARLIEST_BIRTH_YEAR = 1900
_MIN_PASSWORD_LEN = 8
_MAX_PASSWORD_BYTES = 72  # bcrypt silently truncates beyond this


@dataclass
class User:
    """Account plus onboarding profile.

    ``id`` is ``None`` until the row is inserted: the PK is an autoincrement
    integer (the API contract types it as a number), so it does not exist
    before the database assigns it — unlike the other entities, which mint a
    UUID for themselves up front.

    Profile fields are optional because onboarding is progressive: an account
    exists from signup, the body/diet answers arrive over the following screens.
    Lengths are in the user's ``unit_system``; ``height`` is cm and weights are
    kg when metric.
    """

    email: str
    id: int | None = None
    name: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    password_hash: str | None = None  # None for social-login accounts (no password at all)
    email_verified_at: datetime | None = None

    gender: Gender | None = None
    birth_year: int | None = None
    unit_system: UnitSystem = UnitSystem.METRIC
    height: float | None = None
    weight_current: float | None = None
    weight_goal: float | None = None
    activity_level: ActivityLevel | None = None
    diet_type: DietType | None = None
    calorie_calc_mode: CalorieCalcMode = CalorieCalcMode.AUTO
    calorie_left_mode: CalorieLeftMode | None = None
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    weekly_rate_kg: float | None = None

    def __post_init__(self) -> None:
        email = (self.email or "").strip().lower()
        if not _EMAIL_RE.match(email):
            raise InvalidUserAttributeException(
                f"invalid email address: {self.email!r}"
            )
        self.email = email

        # Optional display name: blank collapses to None rather than raising.
        name = (self.name or "").strip()
        self.name = name or None

        if self.birth_year is not None:
            current_year = date.today().year
            if not _EARLIEST_BIRTH_YEAR <= self.birth_year <= current_year:
                raise InvalidUserAttributeException(
                    f"birth_year must be between {_EARLIEST_BIRTH_YEAR} and {current_year}, "
                    f"got {self.birth_year!r}"
                )

        for value, label in (
            (self.height, "height"),
            (self.weight_current, "weight_current"),
            (self.weight_goal, "weight_goal"),
        ):
            if value is not None:
                require_positive(value, label, InvalidUserAttributeException)

        if self.weekly_rate_kg is not None:
            require_non_negative(self.weekly_rate_kg, "weekly_rate_kg", InvalidUserAttributeException)

    @property
    def is_premium(self) -> bool:
        return self.subscription_tier is SubscriptionTier.PREMIUM

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    def verify_email(self, now: datetime) -> None:
        """Mark the address confirmed. Idempotent — re-confirming keeps the first time."""
        if self.email_verified_at is None:
            self.email_verified_at = now

    @staticmethod
    def validate_password_strength(plain: str) -> None:
        """Policy check on a *plaintext* password, before it is hashed and discarded."""
        if len(plain) < _MIN_PASSWORD_LEN:
            raise WeakPasswordException(
                f"password must be at least {_MIN_PASSWORD_LEN} characters"
            )
        if len(plain.encode("utf-8")) > _MAX_PASSWORD_BYTES:
            raise WeakPasswordException(
                f"password must be at most {_MAX_PASSWORD_BYTES} bytes"
            )

    @classmethod
    def create(cls, email: str, name: str | None = None, password_hash: str | None = None) -> User:
        """Factory for a brand-new, not-yet-persisted user: no id yet, active, free tier."""
        return cls(
            email=email,
            name=name,
            is_active=True,
            created_at=datetime.now(UTC),
            password_hash=password_hash,
        )
