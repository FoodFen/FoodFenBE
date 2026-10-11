"""rank_dishes: the diner tab's macro-aware ordering. Pure, no fakes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from src.application.dish_fit import DishFilter, Remaining, fold, rank_dishes
from src.domain.entities.dish import Dish
from src.domain.enums import DietType, DishDiet

_T0 = datetime(2026, 10, 9, tzinfo=UTC)


def _dish(
    kcal: int, *, age_min: int = 0, id_: int | None = None, p: float = 0, c: float = 0, f: float = 0,
    diet: DishDiet = DishDiet.NONE,
) -> Dish:
    d = Dish.create(
        restaurant_id=UUID(int=1), name=f"d{kcal}", price=Decimal(1), serving_g=100, kcal=kcal,
        protein_g=p, carbs_g=c, fat_g=f, diet_tag=diet,
    )
    d.created_at = _T0 - timedelta(minutes=age_min)
    if id_ is not None:
        d.id = UUID(int=id_)
    return d


def _rem(kcal: int, p: float = 0, c: float = 0, f: float = 0) -> Remaining:
    return Remaining(kcal=kcal, protein_g=p, carbs_g=c, fat_g=f)


def _ranked(dishes, remaining, diet=None):
    return [(r.dish.kcal, r.fits) for r in rank_dishes(dishes, remaining, diet)]


def test_no_goal_is_newest_first_nothing_suggested_and_no_reasons():
    old, mid, new = _dish(100, age_min=30), _dish(900, age_min=20), _dish(500, age_min=10)
    ranked = rank_dishes([old, new, mid], None, None)
    assert [r.dish for r in ranked] == [new, mid, old]
    assert all(not r.fits and r.reasons == [] for r in ranked)


def test_no_goal_puts_diet_incompatible_dishes_last():
    veg = _dish(100, age_min=30, diet=DishDiet.VEGAN)
    meat = _dish(100, age_min=1)
    assert [r.dish for r in rank_dishes([meat, veg], None, DietType.VEGAN)] == [veg, meat]


def test_protein_short_user_gets_the_high_protein_dish_first():
    rem = _rem(600, p=80, c=30, f=10)
    carby = _dish(300, p=5, c=50, f=5)
    lean = _dish(300, p=30, c=10, f=5)
    assert [r.dish for r in rank_dishes([carby, lean], rem, None)] == [lean, carby]


def test_keto_user_sinks_a_high_carb_dish_even_if_it_has_fewer_kcal():
    rem = _rem(800, p=60, c=20, f=70)
    carby = _dish(200, p=10, c=40, f=2)
    fatty = _dish(500, p=30, c=5, f=35)
    assert [r.dish for r in rank_dishes([carby, fatty], rem, DietType.KETO)] == [fatty, carby]


def test_tolerance_tier_follows_the_exact_fits_and_both_are_suggested():
    exact = _dish(1000, p=0, c=100)  # worse score, but kcal fits exactly
    over = _dish(1050, p=100)  # within 10%, better score
    way_over = _dish(1101)
    assert _ranked([way_over, over, exact], _rem(1000, p=100), None)[:2] == [(1000, True), (1050, True)]


def test_top_up_suggests_the_lowest_kcal_dishes_up_to_three_with_exceeds_kcal():
    dishes = [_dish(k) for k in (1050, 1500, 1200, 1400, 1300)]
    ranked = rank_dishes(dishes, _rem(1000), None)
    assert [(r.dish.kcal, r.fits) for r in ranked] == [
        (1050, True), (1200, True), (1300, True), (1400, False), (1500, False),
    ]
    assert all("exceeds_kcal" in r.reasons for r in ranked[:3])
    assert all(r.reasons == [] for r in ranked[3:])


def test_nothing_left_still_suggests_three_lowest_kcal():
    dishes = [_dish(k) for k in (300, 100, 200, 400)]
    assert _ranked(dishes, _rem(0), None) == [(100, True), (200, True), (300, True), (400, False)]


def test_ties_are_broken_by_lower_kcal_then_id():
    a, b, c = _dish(400, id_=3), _dish(400, id_=1), _dish(400, id_=2)
    assert [r.dish.id.int for r in rank_dishes([a, b, c], _rem(500), None)] == [1, 2, 3]
    assert [r.dish.id.int for r in rank_dishes([a, b, c], _rem(100), None)] == [1, 2, 3]
    small, big = _dish(300, id_=2), _dish(350, id_=1)
    assert [r.dish.kcal for r in rank_dishes([big, small], _rem(500), None)] == [300, 350]
    same_age = [_dish(1, id_=2), _dish(2, id_=1)]
    assert [r.dish.id.int for r in rank_dishes(same_age, None, None)] == [1, 2]


def test_vegan_user_sees_only_vegan_dishes_suggested_and_the_rest_last_never_topped_up():
    vegan = _dish(900, diet=DishDiet.VEGAN)
    veggie = _dish(100, diet=DishDiet.VEGETARIAN)
    meat = _dish(50)
    ranked = rank_dishes([meat, veggie, vegan], _rem(2000), DietType.VEGAN)
    assert [(r.dish, r.fits) for r in ranked] == [(vegan, True), (meat, False), (veggie, False)]


def test_vegetarian_user_accepts_vegetarian_and_vegan():
    vegan, veggie, meat = _dish(300, diet=DishDiet.VEGAN), _dish(200, diet=DishDiet.VEGETARIAN), _dish(100)
    ranked = rank_dishes([meat, vegan, veggie], _rem(2000), DietType.VEGETARIAN)
    assert [(r.dish, r.fits) for r in ranked] == [(veggie, True), (vegan, True), (meat, False)]


def test_other_or_unset_diet_accepts_every_dish():
    dishes = [_dish(100, diet=DishDiet.VEGAN), _dish(200)]
    for diet in (None, DietType.KETO, DietType.BALANCED):
        assert all(r.fits for r in rank_dishes(dishes, _rem(2000), diet))


def test_reasons_fills_protein_and_exceeds_in_order():
    rem = _rem(500, p=50, c=20, f=10)
    high_protein = _dish(400, p=45, c=10, f=5)  # 0.1125 g/kcal >= 0.1
    assert rank_dishes([high_protein], rem, None)[0].reasons == ["fills_protein"]
    over_all = _dish(540, p=60, c=30, f=20)  # within tolerance, exceeds kcal, carbs and fat
    assert rank_dishes([over_all], rem, None)[0].reasons == [
        "fills_protein", "exceeds_kcal", "exceeds_carbs", "exceeds_fat",
    ]
    low_protein = _dish(400, p=5, c=10, f=5)
    assert rank_dishes([low_protein], rem, None)[0].reasons == []


def test_no_protein_left_means_no_fills_protein_and_extra_protein_is_not_a_problem():
    r = rank_dishes([_dish(100, p=50)], _rem(500, p=0, c=50, f=50), None)[0]
    assert r.fits and r.reasons == []


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
