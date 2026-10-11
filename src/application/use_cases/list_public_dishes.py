"""Use case: the diner tab. Public dishes ordered by what the caller can still eat on ``day``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from src.application.dish_fit import DishFilter, rank_dishes, remaining_on
from src.application.dtos.restaurant import (
    PublicDishDTO,
    PublicDishListDTO,
    PublicFitDishDTO,
    PublicRestaurantSummaryDTO,
)
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

    async def execute(
        self, user_id: int, day: date | None, filters: DishFilter = DishFilter(), offset: int = 0, limit: int = 20
    ) -> PublicDishListDTO:
        """Rank, then filter, then slice ``[offset, offset + limit)``. ``remaining_kcal`` ignores filters and is not clamped."""
        day = day or datetime.now(_VN).date()
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
        # ponytail: offset cursor over the in-memory list; rows shift if the diary changes mid-scroll
        # (the app dedupes by id). Switch to a keyset cursor when ordering moves into SQL.
        end = offset + limit
        return PublicDishListDTO(
            remaining_kcal=remaining_kcal,
            dishes=[
                PublicFitDishDTO(
                    dish=PublicDishDTO.from_entity(r.dish),
                    fits=r.fits,
                    reasons=r.reasons,
                    restaurant=PublicRestaurantSummaryDTO.from_entity(restaurant_of[r.dish.id]),
                )
                for r in shown[offset:end]
            ],
            next_cursor=str(end) if end < len(shown) else None,
        )
