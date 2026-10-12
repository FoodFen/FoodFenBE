"""Use case: the diner tab. Public dishes ordered by what the caller can still eat on ``day``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from src.application.dish_fit import (
    KCAL_TOLERANCE, DishFilter, RankedDish, pick_featured, rank_dishes, remaining_on,
)
from src.application.dtos.restaurant import (
    PublicDishDTO,
    PublicDishListDTO,
    PublicFitDishDTO,
    PublicRestaurantSummaryDTO,
)
from src.application.ports.ad_impression_repository import AdImpressionRepositoryProtocol
from src.application.ports.daily_goal_repository import DailyGoalRepositoryProtocol
from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.application.ports.user_repository import UserRepositoryProtocol

_VN = timezone(timedelta(hours=7))  # Vietnam day, same convention as send_chat_message.py


@dataclass
class ListPublicDishesUseCase:
    restaurants: RestaurantRepositoryProtocol
    daily_goals: DailyGoalRepositoryProtocol
    food_entries: FoodEntryRepositoryProtocol
    users: UserRepositoryProtocol
    ad_impressions: AdImpressionRepositoryProtocol

    async def execute(
        self, user_id: int, day: date | None, filters: DishFilter = DishFilter(), offset: int = 0, limit: int = 20
    ) -> PublicDishListDTO:
        """Rank, then filter, then slice ``[offset, offset + limit)``. ``remaining_kcal`` ignores filters and is not clamped.
        The first page also carries the sponsored section (``featured``), picked from the filtered ranking."""
        now = datetime.now(_VN)
        day = day or now.date()
        remaining_kcal, left = remaining_on(
            await self.daily_goals.list_by_user(user_id),
            await self.food_entries.list_by_date_range(user_id, day, day),
            day,
        )
        user = await self.users.get_by_id(user_id)

        pairs = await self.restaurants.list_public_dishes()
        restaurant_of = {d.id: r for d, r in pairs}
        shown = [
            r for r in rank_dishes((d for d, _ in pairs), left, user.diet_type if user else None)
            if filters.matches(r.dish, restaurant_of[r.dish.id].name, r.fits)
        ]

        def card(r: RankedDish) -> PublicFitDishDTO:
            return PublicFitDishDTO(
                dish=PublicDishDTO.from_entity(r.dish),
                fits=r.fits,
                reasons=r.reasons,
                restaurant=PublicRestaurantSummaryDTO.from_entity(restaurant_of[r.dish.id]),
            )

        featured = []
        if offset == 0 and left is not None:  # no goal: nothing is suggested, so nothing is sponsored
            featured = pick_featured(shown, {r.id for _, r in pairs if r.is_featured(now)}, left.kcal * KCAL_TOLERANCE)
            await self.ad_impressions.increment([f.dish.restaurant_id for f in featured], now.date())
        # ponytail: offset cursor over the in-memory list; rows shift if the diary changes mid-scroll
        # (the app dedupes by id). Switch to a keyset cursor when ordering moves into SQL.
        end = offset + limit
        return PublicDishListDTO(
            remaining_kcal=remaining_kcal,
            dishes=[card(r) for r in shown[offset:end]],
            featured=[card(r) for r in featured],
            next_cursor=str(end) if end < len(shown) else None,
        )
