"""Catalog food — one entry of the server-side food database. All nutrition is per 100 g."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from src.domain.enums import FoodCategory, FoodSourceKind
from src.domain.exceptions import InvalidCatalogFoodException
from src.domain.validation import require_non_empty

_SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_MAX_SLUG = 64
_MAX_NAME = 120  # name and name_en
_MAX_ALIASES, _MAX_ALIAS = 20, 80
_MAX_KCAL = 900
_MAX_SERVINGS, _MAX_LABEL, _MAX_GRAMS = 10, 40, 5000


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
    name_en: str | None
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

    @classmethod
    def create(
        cls,
        slug: str,
        name: str,
        name_en: str | None,
        aliases: list[str],
        category: FoodCategory,
        kcal: int,
        carbs_g: float,
        protein_g: float,
        fat_g: float,
        fiber_g: float | None,
        servings: list[CatalogServing],
        admin_id: int,
        now: datetime,
    ) -> CatalogFood:
        """A food an admin adds: sourced to the team, so it is verified."""
        return cls(
            id=uuid4(), slug=slug, name=name, name_en=name_en, aliases=aliases, category=category,
            source_kind=FoodSourceKind.TEAM, source_ref="team", kcal=kcal, carbs_g=carbs_g, protein_g=protein_g,
            fat_g=fat_g, fiber_g=fiber_g, servings=servings, archived=False, created_at=now, updated_at=now,
            updated_by_admin_id=admin_id,
        )

    def __post_init__(self) -> None:
        exc = InvalidCatalogFoodException
        if len(self.slug) > _MAX_SLUG or not _SLUG.fullmatch(self.slug):
            raise exc(f"slug must be lowercase a-z, 0-9 and single hyphens, at most {_MAX_SLUG} chars, got {self.slug!r}")
        self.name = require_non_empty(self.name, "name", exc)
        if len(self.name) > _MAX_NAME:
            raise exc(f"name must be at most {_MAX_NAME} characters")
        self.name_en = (self.name_en or "").strip() or None
        if self.name_en is not None and len(self.name_en) > _MAX_NAME:
            raise exc(f"name_en must be at most {_MAX_NAME} characters")
        # dict.fromkeys: case-sensitive exact duplicates dropped, order kept.
        self.aliases = list(dict.fromkeys(a for a in (a.strip() for a in self.aliases) if a))
        if len(self.aliases) > _MAX_ALIASES:
            raise exc(f"at most {_MAX_ALIASES} aliases")
        if any(len(a) > _MAX_ALIAS for a in self.aliases):
            raise exc(f"an alias must be at most {_MAX_ALIAS} characters")
        if not 0 <= self.kcal <= _MAX_KCAL:
            raise exc(f"kcal must be from 0 to {_MAX_KCAL}, got {self.kcal!r}")
        for field, value in (("carbs_g", self.carbs_g), ("protein_g", self.protein_g), ("fat_g", self.fat_g)):
            if not 0 <= value <= 100:
                raise exc(f"{field} must be from 0 to 100, got {value!r}")
        if round(self.carbs_g + self.protein_g + self.fat_g, 6) > 100:
            raise exc("carbs_g + protein_g + fat_g must be at most 100 per 100 g")
        if self.fiber_g is not None and not 0 <= self.fiber_g <= 100:
            raise exc(f"fiber_g must be from 0 to 100, got {self.fiber_g!r}")
        if (self.source_kind == FoodSourceKind.LEGACY) != (self.source_ref is None):
            raise exc("source_ref must be set exactly when source_kind is not legacy")
        if not 1 <= len(self.servings) <= _MAX_SERVINGS:
            raise exc(f"a food needs 1 to {_MAX_SERVINGS} servings")
        self.servings = [CatalogServing(s.label.strip(), s.grams, s.default) for s in self.servings]
        if any(not 1 <= len(s.label) <= _MAX_LABEL for s in self.servings):
            raise exc(f"a serving label must be 1 to {_MAX_LABEL} characters")
        if any(not 0 < s.grams <= _MAX_GRAMS for s in self.servings):
            raise exc(f"serving grams must be greater than zero and at most {_MAX_GRAMS}")
        if sum(s.default for s in self.servings) != 1:
            raise exc("exactly one serving must be the default")
