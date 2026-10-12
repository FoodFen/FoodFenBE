"""Order the public dish list by what the caller can still eat today (kcal and macro mix). Standard library only.

Pure so it is tested without fakes; the use case reads the goal and diary.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from datetime import date
from uuid import UUID

from src.domain.entities.daily_goal import DailyGoal
from src.domain.entities.dish import Dish
from src.domain.entities.food_entry import FoodEntry
from src.domain.enums import DietType, DishDiet

# ponytail: every public dish is loaded, sorted and filtered in Python, then sliced per page; push
# ordering + filters into SQL (keyset cursor) when the dish count makes one page's load slow.


KCAL_TOLERANCE = 1.1  # a dish up to 10% over what is left still counts as a suggestion
MIN_SUGGESTED = 3  # a day nearly or fully eaten still gets this many (the least-over dishes)


@dataclass(frozen=True)
class Remaining:
    """What is left of today's goal, each clamped at 0."""

    kcal: int
    protein_g: float
    carbs_g: float
    fat_g: float


def remaining_on(
    goals: Iterable[DailyGoal], eaten: Iterable[FoodEntry], day: date
) -> tuple[int | None, Remaining | None]:
    """The goal in force on ``day`` minus the ``eaten`` entries of that day: the raw remaining kcal (may be
    negative) and the clamped ``Remaining``; ``(None, None)`` when no goal is in force."""
    in_force = [g for g in goals if g.effective_date <= day]
    if not in_force:
        return None, None
    goal, eaten = max(in_force, key=lambda g: g.effective_date), list(eaten)
    kcal = goal.target_kcal - sum(e.total_kcal for e in eaten)
    return kcal, Remaining(
        kcal=max(kcal, 0),
        protein_g=max(goal.target_protein_g - sum(e.protein_g for e in eaten), 0),
        carbs_g=max(goal.target_carbs_g - sum(e.carbs_g for e in eaten), 0),
        fat_g=max(goal.target_fat_g - sum(e.fat_g for e in eaten), 0),
    )


@dataclass(frozen=True)
class RankedDish:
    dish: Dish
    fits: bool  # suggested: tiers 1-2 plus the top-up
    reasons: list[str]


def diet_ok(dish: Dish, diet: DietType | None) -> bool:
    if diet == DietType.VEGAN:
        return dish.diet_tag == DishDiet.VEGAN
    if diet == DietType.VEGETARIAN:
        return dish.diet_tag != DishDiet.NONE
    return True


def _energy_shares(protein_g: float, carbs_g: float, fat_g: float) -> tuple[float, float, float] | None:
    p, c, f = protein_g * 4, carbs_g * 4, fat_g * 9
    total = p + c + f
    return (p / total, c / total, f / total) if total else None


def _score(dish: Dish, left: Remaining) -> float:
    """Lower is better: how far the dish's energy split is from the split of what is left."""
    want = _energy_shares(left.protein_g, left.carbs_g, left.fat_g)
    got = _energy_shares(dish.protein_g, dish.carbs_g, dish.fat_g)
    if want is None or got is None:
        return 0.0
    return max(want[0] - got[0], 0) + max(got[1] - want[1], 0) + max(got[2] - want[2], 0)


def _reasons(dish: Dish, left: Remaining) -> list[str]:
    reasons = []
    if (
        left.protein_g > 0 and left.kcal > 0 and dish.protein_g > 0
        and dish.protein_g * left.kcal >= left.protein_g * dish.kcal  # protein per kcal, no division
    ):
        reasons.append("fills_protein")
    for code, got, rest in (
        ("exceeds_kcal", dish.kcal, left.kcal),
        ("exceeds_carbs", dish.carbs_g, left.carbs_g),
        ("exceeds_fat", dish.fat_g, left.fat_g),
    ):
        if got > rest:
            reasons.append(code)
    return reasons


def rank_dishes(dishes: Iterable[Dish], remaining: Remaining | None, diet: DietType | None) -> list[RankedDish]:
    """Suggested dishes first: those that fit the kcal left (best macro match first), then those within
    ``KCAL_TOLERANCE``, topped up with the lowest-kcal rest to ``MIN_SUGGESTED``. Then the other diet-ok
    dishes by kcal, then diet-incompatible ones by kcal. No goal (``None``): newest first, diet-ok before
    the rest, nothing suggested. The id pre-sort makes ties stable (sorted() is stable)."""
    by_id = sorted(dishes, key=lambda d: d.id)
    ok = [d for d in by_id if diet_ok(d, diet)]
    bad = [d for d in by_id if not diet_ok(d, diet)]
    if remaining is None:
        return [
            RankedDish(d, False, [])
            for group in (ok, bad)
            for d in sorted(group, key=lambda d: d.created_at, reverse=True)
        ]

    def by_score(ds: Iterable[Dish]) -> list[Dish]:
        return sorted(ds, key=lambda d: (_score(d, remaining), d.kcal))

    limit = remaining.kcal * KCAL_TOLERANCE
    suggested = by_score(d for d in ok if d.kcal <= remaining.kcal) + by_score(
        d for d in ok if remaining.kcal < d.kcal <= limit
    )
    over = sorted((d for d in ok if d.kcal > limit), key=lambda d: d.kcal)
    top_up = max(MIN_SUGGESTED - len(suggested), 0)
    suggested += over[:top_up]
    return [RankedDish(d, True, _reasons(d, remaining)) for d in suggested] + [
        RankedDish(d, False, []) for d in over[top_up:] + sorted(bad, key=lambda d: d.kcal)
    ]


def pick_featured(ranked: list[RankedDish], featured_restaurant_ids: set[UUID], limit: int = 3) -> list[RankedDish]:
    """The sponsored section: walking the ranking in order, each featured restaurant's best-ranked
    *suggested* dish, at most ``limit`` restaurants. Money buys eligibility, never a dish that doesn't fit."""
    picked: dict[UUID, RankedDish] = {}
    for r in ranked:
        if len(picked) == limit:
            break
        if r.fits and r.dish.restaurant_id in featured_restaurant_ids:
            picked.setdefault(r.dish.restaurant_id, r)
    return list(picked.values())


def fold(text: str) -> str:
    """Case- and diacritic-insensitive key: "Phở Đà" -> "pho da". đ has no NFD decomposition."""
    nfd = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in nfd if not unicodedata.combining(c)).replace("đ", "d")


@dataclass(frozen=True)
class DishFilter:
    """The dish tab's search + filter chips. ``None`` = no filter; bounds are inclusive."""

    q: str | None = None
    fits: bool | None = None
    kcal_min: float | None = None
    kcal_max: float | None = None
    price_min: int | None = None
    price_max: int | None = None
    protein_min: float | None = None

    def matches(self, dish: Dish, restaurant_name: str, fits: bool) -> bool:
        needle = fold(self.q.strip()) if self.q else ""
        return (
            (not needle or needle in fold(dish.name) or needle in fold(restaurant_name))
            and (self.fits is None or fits == self.fits)
            and (self.kcal_min is None or dish.kcal >= self.kcal_min)
            and (self.kcal_max is None or dish.kcal <= self.kcal_max)
            and (self.price_min is None or dish.price >= self.price_min)
            and (self.price_max is None or dish.price <= self.price_max)
            and (self.protein_min is None or dish.protein_g >= self.protein_min)
        )
