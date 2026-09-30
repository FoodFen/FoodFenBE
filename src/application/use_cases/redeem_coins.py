"""Use case: spend coins on Premium days."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.application.dtos.coin import RedeemOutputDTO
from src.application.dtos.subscription import SubscriptionOutputDTO
from src.application.ports.coin_repository import CoinRepositoryProtocol
from src.application.ports.subscription_repository import SubscriptionRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol
from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.entities.subscription import Subscription
from src.domain.enums import CoinReason, SubscriptionTier
from src.domain.exceptions import InsufficientCoinsException, InvalidAttributeException, UserNotFoundException

# days -> coin cost. ponytail: constants until someone needs to edit bundles without a deploy.
COIN_BUNDLES = {10: 600, 30: 1500}


@dataclass
class RedeemCoinsUseCase:
    coins: CoinRepositoryProtocol
    subscriptions: SubscriptionRepositoryProtocol
    users: UserRepositoryProtocol

    async def execute(self, user_id: int, days: int) -> RedeemOutputDTO:
        cost = COIN_BUNDLES.get(days)
        if cost is None:
            raise InvalidAttributeException(f"days must be one of {sorted(COIN_BUNDLES)}")
        user = await self.users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundException(f"no user {user_id}")

        balance = await self.coins.balance(user_id, for_update=True)
        if balance < cost:
            raise InsufficientCoinsException(f"need {cost} coins, have {balance}")
        await self.coins.add(CoinTransaction.create(user_id, -cost, CoinReason.SPEND))

        existing = await self.subscriptions.get_by_user_id(user_id)
        subscription = await self.subscriptions.save(
            Subscription.grant_days(existing, user_id, days, date.today())
        )
        user.subscription_tier = SubscriptionTier.PREMIUM
        await self.users.update(user)
        return RedeemOutputDTO(
            balance=balance - cost, subscription=SubscriptionOutputDTO.from_entity(subscription)
        )
