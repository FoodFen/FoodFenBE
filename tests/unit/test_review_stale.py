"""Review use cases: optimistic check on expected_updated_at. No I/O."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from src.application.use_cases.review_dish import ReviewDishUseCase
from src.application.use_cases.review_restaurant import ReviewRestaurantUseCase
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.enums import ModerationStatus, ReviewDecision
from src.domain.exceptions import StaleReviewException


class FakeRepo:
    def __init__(self) -> None:
        self.restaurant = Restaurant.create(
            user_id=1, name="R", address="a", phone="1", opening_hours="7-21", latitude=1, longitude=1
        )
        self.dish = Dish.create(
            restaurant_id=self.restaurant.id, name="D", price=Decimal(1), serving_g=1, kcal=1,
            protein_g=0, carbs_g=0, fat_g=0,
        )

    async def get_by_id(self, _id: UUID):
        return self.restaurant

    async def update(self, restaurant) -> None:
        self.restaurant = restaurant

    async def get_dish(self, _id: UUID):
        return self.dish

    async def update_dish(self, dish) -> None:
        self.dish = dish


def _cases(repo: FakeRepo):
    return [
        (ReviewRestaurantUseCase(repo), repo.restaurant, lambda: repo.restaurant),
        (ReviewDishUseCase(repo), repo.dish, lambda: repo.dish),
    ]


@pytest.mark.parametrize("which", [0, 1])
async def test_stale_expected_updated_at_raises_and_changes_nothing(which):
    use_case, row, current = _cases(FakeRepo())[which]
    stale = row.updated_at - timedelta(seconds=1)
    with pytest.raises(StaleReviewException):
        await use_case.execute(row.id, ReviewDecision.APPROVED, None, stale)
    assert current().status == ModerationStatus.PENDING and current().reviewed_at is None


@pytest.mark.parametrize("which", [0, 1])
@pytest.mark.parametrize("matching", [True, False])
async def test_matching_or_absent_expected_updated_at_reviews(which, matching):
    use_case, row, current = _cases(FakeRepo())[which]
    result = await use_case.execute(row.id, ReviewDecision.APPROVED, None, row.updated_at if matching else None)
    assert result.status == ModerationStatus.APPROVED and current().status == ModerationStatus.APPROVED
