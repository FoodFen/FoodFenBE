"""Order the public dish list by what the caller can still eat today. Standard library only.

Pure so it is tested without fakes; the use case reads the goal and diary.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from src.domain.entities.dish import Dish

# ponytail: every public dish is loaded, sorted and filtered in Python, then sliced per page; push
# ordering + filters into SQL (keyset cursor) when the dish count makes one page's load slow.


def rank_dishes(dishes: Iterable[Dish], remaining_kcal: int | None) -> list[tuple[Dish, bool]]:
    """``(dish, fits)`` pairs. Fitting dishes first, highest kcal first (closest to filling what is
    left); then the rest, lowest kcal first. No goal (``None``): nothing fits, newest first.
    The id pre-sort makes ties stable (sorted() is stable)."""
    by_id = sorted(dishes, key=lambda d: d.id)
    if remaining_kcal is None:
        return [(d, False) for d in sorted(by_id, key=lambda d: d.created_at, reverse=True)]
    fits = sorted((d for d in by_id if d.kcal <= remaining_kcal), key=lambda d: -d.kcal)
    rest = sorted((d for d in by_id if d.kcal > remaining_kcal), key=lambda d: d.kcal)
    return [(d, True) for d in fits] + [(d, False) for d in rest]


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
