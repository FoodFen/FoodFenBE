"""Catalog food factory shared by the grounding / provider / use-case unit tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from src.domain.entities.catalog_food import CatalogFood, CatalogServing
from src.domain.enums import FoodCategory, FoodSourceKind

NOW = datetime(2026, 11, 1, tzinfo=UTC)


def make_food(slug: str = "pho-bo", **over) -> CatalogFood:
    base = dict(
        id=uuid4(), slug=slug, name="Phở bò", aliases=["pho", "beef noodle soup"],
        category=FoodCategory.MON_NUOC, source_kind=FoodSourceKind.NIN, source_ref="nin:1",
        kcal=81, carbs_g=10.2, protein_g=4.5, fat_g=2.4, fiber_g=0.2,
        servings=[CatalogServing("1 tô", 550, True), CatalogServing("nửa tô", 275)],
        archived=False, created_at=NOW, updated_at=NOW, updated_by_admin_id=None,
    )
    return CatalogFood(**{**base, **over})
