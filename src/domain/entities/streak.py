"""Streak entity — one row per user, tracking consecutive active days."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from src.domain.exceptions import InvalidAttributeException
from src.domain.validation import require_non_negative


@dataclass
class Streak:
    id: UUID
    user_id: UUID
    current_streak: int = 0
    longest_streak: int = 0
    last_active_date: date | None = None

    def __post_init__(self) -> None:
        require_non_negative(self.current_streak, "current_streak")
        require_non_negative(self.longest_streak, "longest_streak")
        if self.current_streak > self.longest_streak:
            raise InvalidAttributeException(
                f"longest_streak ({self.longest_streak}) must be at least "
                f"current_streak ({self.current_streak})"
            )

    @classmethod
    def create(cls, user_id: UUID) -> Streak:
        """A fresh streak: nothing logged yet."""
        return cls(id=uuid4(), user_id=user_id)
