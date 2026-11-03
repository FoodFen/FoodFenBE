from datetime import UTC, datetime
from uuid import uuid4

import importlib.util
import json
from pathlib import Path

import pytest

from src.domain.entities.catalog_food import CatalogFood, CatalogServing
from src.domain.enums import FoodCategory, FoodSourceKind
from src.domain.exceptions import InvalidCatalogFoodException

_ROOT = Path(__file__).resolve().parents[2]

NOW = datetime(2026, 11, 1, tzinfo=UTC)


def _food(**over) -> CatalogFood:
    base = dict(
        id=uuid4(), slug="banh-bao", name="Bánh bao", name_en=None, aliases=[], category=FoodCategory.AN_VAT,
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


@pytest.mark.parametrize(
    "over",
    [
        {"name": "x" * 121},
        {"name_en": "x" * 121},
        {"aliases": ["x" * 81]},
        {"aliases": [f"a{i}" for i in range(21)]},
        {"kcal": 901},
        {"carbs_g": 100.1},
        {"protein_g": 100.1},
        {"fat_g": 100.1},
        {"carbs_g": 60, "protein_g": 30, "fat_g": 20},  # sum > 100
        {"fiber_g": 100.1},
        {"servings": [CatalogServing(f"s{i}", 10, i == 0) for i in range(11)]},
        {"servings": [CatalogServing("", 10, True)]},
        {"servings": [CatalogServing("x" * 41, 10, True)]},
        {"servings": [CatalogServing("a", 5001, True)]},
    ],
)
def test_admin_limits(over):
    with pytest.raises(InvalidCatalogFoodException):
        _food(**over)


def test_boundaries_are_valid():
    _food(name="x" * 120, name_en="x" * 120, aliases=["x" * 80] * 1, kcal=900, carbs_g=100, protein_g=0, fat_g=0, fiber_g=100)
    _food(aliases=[f"a{i}" for i in range(20)], servings=[CatalogServing("a" * 40, 5000, True)])


def test_text_fields_are_cleaned():
    f = _food(
        name="  Bánh bao ", name_en="  ", aliases=[" bao ", "", "bao", "Bao", "  "],
        servings=[CatalogServing(" 1 cái ", 120, True)],
    )
    assert (f.name, f.name_en, f.aliases) == ("Bánh bao", None, ["bao", "Bao"])
    assert f.servings == [CatalogServing("1 cái", 120, True)]
    assert _food(name_en=" bao ").name_en == "bao"


def test_create_is_a_verified_team_food():
    f = CatalogFood.create(
        "x", "X", None, [], FoodCategory.COM, 100, 10, 5, 2, None, [CatalogServing("1", 100, True)], 7, NOW
    )
    assert (f.source_kind, f.source_ref, f.archived, f.verified) == (FoodSourceKind.TEAM, "team", False, True)
    assert (f.updated_by_admin_id, f.created_at, f.updated_at) == (7, NOW, NOW)
    assert f.id is not None


def test_every_seed_food_is_valid_for_the_entity():
    spec = importlib.util.spec_from_file_location("m0033", _ROOT / "alembic/versions/0033_food_catalog.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    foods = json.loads((_ROOT / "alembic/data/foods.json").read_text(encoding="utf-8"))
    for row in mod._rows(foods):
        CatalogFood(
            **{**row, "category": FoodCategory(row["category"]), "source_kind": FoodSourceKind(row["source_kind"]),
               "servings": [CatalogServing(**s) for s in row["servings"]], "name_en": None}
        )
