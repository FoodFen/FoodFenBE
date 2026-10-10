"""rank_dishes: the diner tab's ordering. Pure, no fakes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from src.application.dish_fit import DishFilter, fold, rank_dishes
from src.domain.entities.dish import Dish

_T0 = datetime(2026, 10, 9, tzinfo=UTC)


def _dish(kcal: int, *, age_min: int = 0, id_: int | None = None) -> Dish:
    d = Dish.create(
        restaurant_id=UUID(int=1), name=f"d{kcal}", price=Decimal(1), serving_g=100, kcal=kcal,
        protein_g=0, carbs_g=0, fat_g=0,
    )
    d.created_at = _T0 - timedelta(minutes=age_min)
    if id_ is not None:
        d.id = UUID(int=id_)
    return d


def _ranked(dishes, remaining):
    return [(d.kcal, fits) for d, fits in rank_dishes(dishes, remaining)]


def test_no_goal_is_newest_first_and_nothing_fits():
    old, mid, new = _dish(100, age_min=30), _dish(900, age_min=20), _dish(500, age_min=10)
    assert [d for d, _ in rank_dishes([old, new, mid], None)] == [new, mid, old]
    assert all(not fits for _, fits in rank_dishes([old, new, mid], None))


def test_fitting_dishes_first_high_to_low_then_rest_low_to_high():
    dishes = [_dish(k) for k in (300, 900, 700, 1200, 100)]
    assert _ranked(dishes, 800) == [
        (700, True), (300, True), (100, True), (900, False), (1200, False),
    ]


def test_remaining_at_or_below_zero_fits_nothing_and_orders_low_to_high():
    dishes = [_dish(k) for k in (300, 100, 200)]
    assert _ranked(dishes, 0) == [(100, False), (200, False), (300, False)]
    assert _ranked(dishes, -50) == [(100, False), (200, False), (300, False)]


def test_ties_keep_a_stable_order_by_id():
    a, b, c = _dish(400, id_=3), _dish(400, id_=1), _dish(400, id_=2)
    assert [d.id.int for d, _ in rank_dishes([a, b, c], 500)] == [1, 2, 3]
    assert [d.id.int for d, _ in rank_dishes([a, b, c], 100)] == [1, 2, 3]
    same_age = [_dish(1, id_=2), _dish(2, id_=1)]
    assert [d.id.int for d, _ in rank_dishes(same_age, None)] == [1, 2]


def test_fold_strips_case_and_vietnamese_diacritics():
    assert fold("Phở Bò ĐẶC BIỆT") == "pho bo dac biet"


def test_dish_filter_bounds_are_inclusive_and_q_matches_restaurant_too():
    d = _dish(500)
    d.name, d.price, d.protein_g = "Bún chả", Decimal(40000), 25
    assert DishFilter().matches(d, "Quán", fits=False)
    assert DishFilter(q="  bun CHA ", kcal_min=500, kcal_max=500, price_min=40000, price_max=40000,
                      protein_min=25, fits=True).matches(d, "Quán", fits=True)
    assert DishFilter(q="quan").matches(d, "Quán Ngon", fits=False)
    assert DishFilter(q="   ").matches(d, "x", fits=False)
    for f in (DishFilter(q="pho"), DishFilter(fits=True), DishFilter(kcal_min=501), DishFilter(kcal_max=499),
              DishFilter(price_min=40001), DishFilter(price_max=39999), DishFilter(protein_min=25.5)):
        assert not f.matches(d, "Quán", fits=False), f
