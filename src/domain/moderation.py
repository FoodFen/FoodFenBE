"""Moderation rules shared by Restaurant and Dish. Standard library only."""

from __future__ import annotations

from src.domain.enums import ModerationStatus
from src.domain.exceptions import InvalidRestaurantAttributeException


def checked_reason(status: ModerationStatus, reason: str | None) -> str | None:
    """The rejection reason to store for ``status``: required when rejected, dropped otherwise."""
    if status != ModerationStatus.REJECTED:
        return None
    text = (reason or "").strip()
    if not text:
        raise InvalidRestaurantAttributeException("a rejection reason is required")
    return text
