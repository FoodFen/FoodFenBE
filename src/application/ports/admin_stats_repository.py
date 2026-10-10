"""Raw rows for the admin dashboard; bucketing into days is the use case's job."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from src.domain.entities.streak import Streak
from src.domain.entities.subscription import Subscription
from src.domain.entities.user import User


class AdminStatsRepositoryProtocol(Protocol):
    """All ranges are ``[start, end)`` in aware UTC instants; returned instants are aware."""

    async def paid_payments(self, start: datetime, end: datetime) -> list[tuple[datetime, Decimal]]:
        """``(paid_at, amount)`` of payments with status ``paid``, by ``paid_at``."""
        ...

    async def user_signups(self, start: datetime, end: datetime) -> list[datetime]: ...

    async def restaurant_signups(self, start: datetime, end: datetime) -> list[datetime]: ...

    async def food_entry_days(self, first: date, last: date) -> list[date]:
        """``logged_on`` of every non-deleted food entry, for days ``first..last`` inclusive."""
        ...

    async def accounts(self) -> list[tuple[User, Subscription | None, Streak | None]]:
        """Every user with their subscription and streak rows, in no particular order."""
        ...
