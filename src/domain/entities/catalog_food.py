"""Catalog food — one entry of the server-side food database. All nutrition is per 100 g."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.domain.enums import FoodCategory, FoodSourceKind
from src.domain.exceptions import InvalidCatalogFoodException
from src.domain.validation import require_non_empty, require_non_negative

_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_MAX_SLUG = 64


@dataclass(frozen=True)
class CatalogServing:
    label: str
    grams: int
    default: bool = False


@dataclass
class CatalogFood:
    id: UUID
    slug: str
    name: str
    aliases: list[str]
    category: FoodCategory
    source_kind: FoodSourceKind
    source_ref: str | None
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None
    servings: list[CatalogServing]
    archived: bool
    created_at: datetime
    updated_at: datetime
    updated_by_admin_id: int | None

    @property
    def verified(self) -> bool:
        return self.source_kind != FoodSourceKind.LEGACY

    def __post_init__(self) -> None:
        exc = InvalidCatalogFoodException
        if len(self.slug) > _MAX_SLUG or not _SLUG.fullmatch(self.slug):
            raise exc(f"slug must be lowercase a-z, 0-9 and single hyphens, at most {_MAX_SLUG} chars, got {self.slug!r}")
        self.name = require_non_empty(self.name, "name", exc)
        for field, value in (("kcal", self.kcal), ("carbs_g", self.carbs_g), ("protein_g", self.protein_g), ("fat_g", self.fat_g)):
            require_non_negative(value, field, exc)
        if self.fiber_g is not None:
            require_non_negative(self.fiber_g, "fiber_g", exc)
        if (self.source_kind == FoodSourceKind.LEGACY) != (self.source_ref is None):
            raise exc("source_ref must be set exactly when source_kind is not legacy")
        if not self.servings:
            raise exc("a food needs at least one serving")
        if any(s.grams <= 0 for s in self.servings):
            raise exc("serving grams must be greater than zero")
        if sum(s.default for s in self.servings) != 1:
            raise exc("exactly one serving must be the default")
