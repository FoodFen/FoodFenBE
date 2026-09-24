"""Use case: read the current user's subscription, if any."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.subscription import SubscriptionOutputDTO
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol


@dataclass
class GetMySubscriptionUseCase:
    subscriptions: SubscriptionRepositoryProtocol

    async def execute(self, user_id: int) -> SubscriptionOutputDTO | None:
        subscription = await self.subscriptions.get_by_user_id(user_id)
        return SubscriptionOutputDTO.from_entity(subscription) if subscription is not None else None
