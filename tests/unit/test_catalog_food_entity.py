from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.domain.entities.catalog_food import CatalogFood, CatalogServing
from src.domain.enums import FoodCategory, FoodSourceKind
from src.domain.exceptions import InvalidCatalogFoodException

NOW = datetime(2026, 11, 1, tzinfo=UTC)


def _food(**over) -> CatalogFood:
    base = dict(
        id=uuid4(), slug="banh-bao", name="Bánh bao", aliases=[], category=FoodCategory.AN_VAT,
        source_kind=FoodSourceKind.NIN, source_ref="nin:1009", kcal=219, carbs_g=47.5, protein_g=6.1,
        fat_g=0.5, fiber_g=0.5, servings=[CatalogServing("1 cái", 120, True), CatalogServing("nửa", 60)],
        archived=False, created_at=NOW, updated_at=NOW, updated_by_admin_id=None,
    )
    return CatalogFood(**{**base, **over})


def test_verified_is_false_only_for_legacy():
    for kind in FoodSourceKind:
        ref = None if kind == FoodSourceKind.LEGACY else "x"
        assert _food(source_kind=kind, source_ref=ref).verified is (kind != FoodSourceKind.LEGACY)


def test_valid_food_with_no_fiber():
    assert _food(fiber_g=None).fiber_g is None


@pytest.mark.parametrize(
    "over",
    [
        {"slug": "Bad Slug"},
        {"slug": "-x"},
        {"slug": "a--b"},
        {"slug": "a" * 65},
        {"name": "  "},
        {"kcal": -1},
        {"carbs_g": -0.1},
        {"protein_g": -0.1},
        {"fat_g": -0.1},
        {"fiber_g": -0.1},
        {"source_kind": FoodSourceKind.LEGACY},  # legacy with a source_ref
        {"source_ref": None},  # non-legacy without one
        {"servings": []},
        {"servings": [CatalogServing("a", 0, True)]},
        {"servings": [CatalogServing("a", 10), CatalogServing("b", 20)]},  # no default
        {"servings": [CatalogServing("a", 10, True), CatalogServing("b", 20, True)]},  # two defaults
    ],
)
def test_invariants(over):
    with pytest.raises(InvalidCatalogFoodException):
        _food(**over)


def test_legacy_without_ref_is_valid():
    assert not _food(source_kind=FoodSourceKind.LEGACY, source_ref=None).verified
