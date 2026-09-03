"""User entity. Standard library only — invariants enforced on construction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.enums import (
    ActivityLevel,
    CalorieCalcMode,
    DietType,
    Gender,
    SubscriptionTier,
    UnitSystem,
)
from src.domain.exceptions import InvalidUserAttributeException, WeakPasswordException
from src.domain.validation import require_positive

# Deliberately permissive: "something@something.something", no whitespace.
# ponytail: naive regex, swap for a real RFC 5322 validator only if bad addresses reach production.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_EARLIEST_BIRTH_YEAR = 1900
_MIN_PASSWORD_LEN = 8
_MAX_PASSWORD_BYTES = 72  # bcrypt silently truncates beyond this


@dataclass
class User:
    """Account plus onboarding profile.

    Profile fields are optional because onboarding is progressive: an account
    exists from signup, the body/diet answers arrive over the following screens.
    Lengths are in the user's ``unit_system``; ``height`` is cm and weights are
    kg when metric.
    """

    id: UUID
    email: str
    name: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Auth. Nullable: social-login accounts never set one, and the hashing
    # itself belongs to an infrastructure adapter, not the domain.
    password_hash: str | None = None

    # Onboarding profile.
    gender: Gender | None = None
    birth_year: int | None = None
    unit_system: UnitSystem = UnitSystem.METRIC
    height: float | None = None
    weight_current: float | None = None
    weight_goal: float | None = None
    activity_level: ActivityLevel | None = None
    diet_type: DietType | None = None
    calorie_calc_mode: CalorieCalcMode = CalorieCalcMode.AUTO
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE

    def __post_init__(self) -> None:
        email = (self.email or "").strip().lower()
        if not _EMAIL_RE.match(email):
            raise InvalidUserAttributeException(
                f"invalid email address: {self.email!r}"
            )
        self.email = email

        name = (self.name or "").strip()
        if not name:
            raise InvalidUserAttributeException("user name must not be empty")
        self.name = name

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

    @property
    def is_premium(self) -> bool:
        return self.subscription_tier is SubscriptionTier.PREMIUM

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
    def create(cls, email: str, name: str, password_hash: str | None = None) -> User:
        """Factory for a brand-new user: fresh id, active, free tier, created now."""
        return cls(
            id=uuid4(),
            email=email,
            name=name,
            is_active=True,
            created_at=datetime.now(UTC),
            password_hash=password_hash,
        )
