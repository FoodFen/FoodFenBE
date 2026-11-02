"""Review use cases: an owner notice only when a status really changes (dish approvals stay silent)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.application.use_cases.review_dish import ReviewDishUseCase
from src.application.use_cases.review_restaurant import ReviewRestaurantUseCase
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.entities.user import User
from src.domain.enums import ReviewDecision


class FakeRepo:
    def __init__(self) -> None:
        self.restaurant = Restaurant.create(
            user_id=7, name="Quan Ngon", address="a", phone="1", opening_hours="7-21", latitude=1, longitude=1
        )
        self.dish = Dish.create(
            restaurant_id=self.restaurant.id, name="Pho", price=Decimal(1), serving_g=1, kcal=1,
            protein_g=0, carbs_g=0, fat_g=0,
        )

    async def get_by_id(self, _id):
        return self.restaurant

    async def update(self, restaurant) -> None: ...

    async def get_dish(self, _id):
        return self.dish

    async def update_dish(self, dish) -> None: ...


class FakeUsers:
    async def get_by_id(self, user_id: int):
        assert user_id == 7
        return User(id=7, email="owner@example.com", password_hash="x", name="Ann")


async def test_restaurant_approved_then_repeat_notifies_once():
    repo = FakeRepo()
    use_case = ReviewRestaurantUseCase(repo, FakeUsers())
    first = await use_case.execute(repo.restaurant.id, ReviewDecision.APPROVED, None, None)
    assert (first.notice.email, first.notice.approved, first.notice.restaurant_name) == (
        "owner@example.com", True, "Quan Ngon",
    )
    again = await use_case.execute(repo.restaurant.id, ReviewDecision.APPROVED, None, None)
    assert again.notice is None


async def test_restaurant_rejection_carries_reason_and_takedown_notifies():
    repo = FakeRepo()
    use_case = ReviewRestaurantUseCase(repo, FakeUsers())
    await use_case.execute(repo.restaurant.id, ReviewDecision.APPROVED, None, None)
    down = await use_case.execute(repo.restaurant.id, ReviewDecision.REJECTED, "food safety", None)
    assert (down.notice.approved, down.notice.reason) == (False, "food safety")


async def test_dish_rejection_notifies_with_dish_name_and_reason():
    repo = FakeRepo()
    use_case = ReviewDishUseCase(repo, FakeUsers())
    result = await use_case.execute(repo.dish.id, ReviewDecision.REJECTED, "kcal is wrong", None)
    n = result.notice
    assert (n.dish_name, n.restaurant_name, n.reason, n.approved) == ("Pho", "Quan Ngon", "kcal is wrong", False)
    again = await use_case.execute(repo.dish.id, ReviewDecision.REJECTED, "kcal is wrong", None)
    assert again.notice is None


@pytest.mark.parametrize("first", [None, ReviewDecision.REJECTED])
async def test_dish_approval_never_notifies(first):
    repo = FakeRepo()
    use_case = ReviewDishUseCase(repo, FakeUsers())
    if first is not None:
        await use_case.execute(repo.dish.id, first, "x", None)
    assert (await use_case.execute(repo.dish.id, ReviewDecision.APPROVED, None, None)).notice is None
