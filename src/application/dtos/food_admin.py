"""Admin food catalog DTOs — frozen dataclasses, never Pydantic models or ORM rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import EllipsisType
from uuid import UUID

from src.domain.entities.catalog_food import CatalogFood
from src.domain.enums import FoodCategory, FoodChangeAction, FoodMissStatus, FoodSourceKind


@dataclass(frozen=True)
class FoodServingDTO:
    label: str
    grams: int
    default: bool


@dataclass(frozen=True)
class AdminFoodDTO:
    """A catalog food. The list shows the row fields only; ``updated_by_email`` is filled on single-food reads."""

    slug: str
    name: str
    name_en: str | None
    category: FoodCategory
    source_kind: FoodSourceKind
    source_ref: str | None
    verified: bool
    kcal: int
    carbs_g: float
    protein_g: float
    fat_g: float
    fiber_g: float | None
    archived: bool
    updated_at: datetime
    aliases: list[str]
    servings: list[FoodServingDTO]
    created_at: datetime
    updated_by_email: str | None

    @classmethod
    def from_entity(cls, f: CatalogFood, updated_by_email: str | None = None) -> AdminFoodDTO:
        return cls(
            f.slug, f.name, f.name_en, f.category, f.source_kind, f.source_ref, f.verified, f.kcal, f.carbs_g,
            f.protein_g, f.fat_g, f.fiber_g, f.archived, f.updated_at, list(f.aliases),
            [FoodServingDTO(s.label, s.grams, s.default) for s in f.servings], f.created_at, updated_by_email,
        )


@dataclass(frozen=True)
class AdminFoodListDTO:
    foods: list[AdminFoodDTO]
    total: int
    next_cursor: str | None


@dataclass(frozen=True)
class FoodEditDTO:
    """A partial edit: ``...`` = keep. Only ``name_en`` and ``fiber_g`` may be ``None`` (= clear)."""

    name: str | EllipsisType = ...
    name_en: str | None | EllipsisType = ...
    aliases: list[str] | EllipsisType = ...
    category: FoodCategory | EllipsisType = ...
    kcal: int | EllipsisType = ...
    carbs_g: float | EllipsisType = ...
    protein_g: float | EllipsisType = ...
    fat_g: float | EllipsisType = ...
    fiber_g: float | None | EllipsisType = ...
    servings: list[FoodServingDTO] | EllipsisType = ...


@dataclass(frozen=True)
class FoodChangeDTO:
    id: UUID
    action: FoodChangeAction
    admin_email: str | None
    created_at: datetime
    before: dict | None  # snake_case snapshot; the adapter camelCases its keys
    after: dict


@dataclass(frozen=True)
class ExistingFoodDTO:
    slug: str
    name: str


@dataclass(frozen=True)
class FoodMissDTO:
    id: UUID
    key: str
    name: str
    language: str
    count: int
    first_seen_at: datetime
    last_seen_at: datetime
    status: FoodMissStatus
    existing_food: ExistingFoodDTO | None


@dataclass(frozen=True)
class FoodMissListDTO:
    misses: list[FoodMissDTO]
    total: int
    next_cursor: str | None
