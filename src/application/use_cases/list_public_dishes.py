"""Use case: the diner tab. Public dishes ordered by what the caller can still eat on ``day``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from src.application.dish_fit import DishFilter, Remaining, rank_dishes
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
        in_force = [g for g in await self.daily_goals.list_by_user(user_id) if g.effective_date <= day]
        remaining_kcal = left = None
        if in_force:
            goal = max(in_force, key=lambda g: g.effective_date)
            eaten = await self.food_entries.list_by_date_range(user_id, day, day)
            remaining_kcal = goal.target_kcal - sum(e.total_kcal for e in eaten)
            left = Remaining(
                kcal=max(remaining_kcal, 0),
                protein_g=max(goal.target_protein_g - sum(e.protein_g for e in eaten), 0),
                carbs_g=max(goal.target_carbs_g - sum(e.carbs_g for e in eaten), 0),
                fat_g=max(goal.target_fat_g - sum(e.fat_g for e in eaten), 0),
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
