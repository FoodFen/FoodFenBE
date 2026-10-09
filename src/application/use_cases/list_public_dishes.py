"""Use case: the diner tab. Public dishes ordered by what the caller can still eat on ``day``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from src.application.dish_fit import rank_dishes
from src.application.dtos.restaurant import (
    PublicDishDTO,
    PublicDishListDTO,
    PublicFitDishDTO,
    PublicRestaurantSummaryDTO,
)
from src.application.ports.daily_goal_repository import DailyGoalRepositoryProtocol
from src.application.ports.food_entry_repository import FoodEntryRepositoryProtocol
from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol

_VN = timezone(timedelta(hours=7))  # Vietnam day, same convention as send_chat_message.py


@dataclass
class ListPublicDishesUseCase:
    restaurants: RestaurantRepositoryProtocol
    daily_goals: DailyGoalRepositoryProtocol
    food_entries: FoodEntryRepositoryProtocol

    async def execute(self, user_id: int, day: date | None) -> PublicDishListDTO:
        day = day or datetime.now(_VN).date()
        in_force = [g for g in await self.daily_goals.list_by_user(user_id) if g.effective_date <= day]
        remaining = None
        if in_force:
            goal = max(in_force, key=lambda g: g.effective_date)
            eaten = sum(e.total_kcal for e in await self.food_entries.list_by_date_range(user_id, day, day))
            remaining = goal.target_kcal - eaten

        pairs = await self.restaurants.list_public_dishes()
        restaurant_of = {d.id: r for d, r in pairs}
        return PublicDishListDTO(
            remaining_kcal=remaining,
            dishes=[
                PublicFitDishDTO(
                    dish=PublicDishDTO.from_entity(d),
                    fits=fits,
                    restaurant=PublicRestaurantSummaryDTO.from_entity(restaurant_of[d.id]),
                )
                for d, fits in rank_dishes((d for d, _ in pairs), remaining)
            ],
        )
