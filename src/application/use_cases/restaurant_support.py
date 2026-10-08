"""Ownership resolution shared by the owner use cases. A user owns at most one restaurant,
so "mine" needs no id: ownership is implied, and someone else's dish is simply not found."""

from __future__ import annotations

from uuid import UUID

from src.application.ports.restaurant_repository import RestaurantRepositoryProtocol
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.exceptions import DishNotFoundException, RestaurantNotFoundException


async def owned_restaurant(restaurants: RestaurantRepositoryProtocol, user_id: int) -> Restaurant:
    restaurant = await restaurants.get_by_owner(user_id)
    if restaurant is None:
        raise RestaurantNotFoundException("you have no restaurant yet")
    return restaurant


async def owned_dish(
    restaurants: RestaurantRepositoryProtocol, user_id: int, dish_id: UUID
) -> Dish:
    restaurant = await owned_restaurant(restaurants, user_id)
    dish = await restaurants.get_dish(dish_id)
    if dish is None or dish.restaurant_id != restaurant.id:
        raise DishNotFoundException(f"dish {dish_id} not found")  # 404, never 403: no existence leak
    return dish
