"""Persistence port for subscriptions. Structural typing via Protocol."""

from __future__ import annotations

from typing import Protocol

from src.domain.entities.subscription import Subscription


class SubscriptionRepositoryProtocol(Protocol):
    async def get_by_user_id(self, user_id: int) -> Subscription | None: ...

    async def save(self, subscription: Subscription) -> Subscription:
        """Upsert keyed on ``user_id`` — at most one row per user."""
        ...
