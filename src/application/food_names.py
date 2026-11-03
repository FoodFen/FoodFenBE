"""How food names are normalised: the key of an unmatched AI name, and of the names a catalog food answers to."""

from __future__ import annotations

import re

from src.application.dish_fit import fold
from src.domain.entities.catalog_food import CatalogFood

_COUNT_SUFFIX = re.compile(r"\s*\(x\s*\d+\)\s*$", re.I)  # the model writes "Egg (x3)"
_MAX_KEY = 120


def clean_name(name: str) -> str:
    """The display form of an unmatched name: no count suffix, no trailing punctuation."""
    return _COUNT_SUFFIX.sub("", name).strip().rstrip(".,;:!?… \t").strip()


def miss_key(name: str) -> str:
    return fold(clean_name(name))[:_MAX_KEY]


def food_keys(food: CatalogFood) -> set[str]:
    """Every miss key this food answers to: its name, English name and aliases."""
    names = [food.name, food.name_en or "", *food.aliases]
    return {k for k in map(miss_key, names) if k}


def slugify(name: str) -> str:
    """``fold`` the name to lowercase ASCII words joined by ``-``, at most 60 chars (room for a ``-2`` suffix)."""
    return re.sub(r"[^a-z0-9]+", "-", fold(name)).strip("-")[:60].strip("-") or "food"
