"""Order the public dish list by what the caller can still eat today. Standard library only.

Pure so it is tested without fakes; the use case reads the goal and diary.
"""

from __future__ import annotations

from collections.abc import Iterable

from src.domain.entities.dish import Dish

# ponytail: every public dish is loaded and sorted in Python; when the payload gets heavy, add
# pagination and push the ordering into SQL.


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
