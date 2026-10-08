"""Raw rows for the admin dashboard; bucketing into days is the use case's job."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol


class AdminStatsRepositoryProtocol(Protocol):
    """All ranges are ``[start, end)`` in aware UTC instants; returned instants are aware."""

    async def paid_payments(self, start: datetime, end: datetime) -> list[tuple[datetime, Decimal]]:
        """``(paid_at, amount)`` of payments with status ``paid``, by ``paid_at``."""
        ...

    async def user_signups(self, start: datetime, end: datetime) -> list[datetime]: ...

    async def restaurant_signups(self, start: datetime, end: datetime) -> list[datetime]: ...
