"""Read-only account status rules shared by the admin screens and the premium reconciliation.
Standard library only."""

from __future__ import annotations

from datetime import date, timedelta

from src.domain.entities.streak import Streak
from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User


def is_premium_today(user: User, subscription: Subscription | None, today: date) -> bool:
    """Premium flag set and no lapsed subscription. A flag with no subscription row counts (it was
    set by hand), exactly as ``_reconcile_premium`` treats it; this never writes the reconciliation."""
    return user.is_premium and (subscription is None or subscription.covers(today))


def shown_streak(streak: Streak | None, today: date) -> int:
    """The streak as it stands today: a missed day (last active before yesterday) broke it."""
    if streak is None or streak.last_active_date is None:
        return 0
    return streak.current_streak if streak.last_active_date >= today - timedelta(days=1) else 0
