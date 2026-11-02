import importlib.util
import json
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("m0033", _ROOT / "alembic/versions/0033_food_catalog.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_FOODS = json.loads((_ROOT / "alembic/data/foods.json").read_text(encoding="utf-8"))
_ROWS = _mod._rows(_FOODS)
_BY_SLUG = {r["slug"]: r for r in _ROWS}


def test_one_row_per_food_with_unique_slugs():
    assert len(_FOODS) == len(_ROWS) == len(_BY_SLUG) == 670
    assert len({r["id"] for r in _ROWS}) == 670


def test_ids_are_deterministic():
    assert _mod._rows(_FOODS)[0]["id"] == _ROWS[0]["id"]


def test_nutrition_copied_exactly_and_missing_fiber_stays_none():
    no_fiber = []
    for f in _FOODS:
        row, per = _BY_SLUG[f["id"]], f["per100g"]
        assert (row["kcal"], row["carbs_g"], row["protein_g"], row["fat_g"]) == (
            per["kcal"], per["carbsG"], per["proteinG"], per["fatG"],
        )
        assert row["fiber_g"] == per.get("fiberG")
        if "fiberG" not in per:
            no_fiber.append(row)
    assert len(no_fiber) == 4
    assert all(r["fiber_g"] is None for r in no_fiber)


def test_source_kinds_and_refs():
    assert Counter(r["source_kind"] for r in _ROWS) == {"nin": 144, "usda": 162, "recipe": 350, "legacy": 14}
    for f in _FOODS:
        row = _BY_SLUG[f["id"]]
        if row["source_kind"] == "recipe":
            assert row["source_ref"] == "recipe"
        elif row["source_kind"] == "legacy":
            assert row["source_ref"] is None
        else:
            assert row["source_ref"] == f["sourceRef"]
            assert row["source_ref"].startswith(row["source_kind"] + ":")


def test_yakult_is_legacy_with_zero_fiber():
    row = _BY_SLUG["yakult"]
    assert row["source_kind"] == "legacy"
    assert row["source_ref"] is None
    assert row["fiber_g"] == 0


def test_servings_have_no_ids_and_one_default():
    for row in _ROWS:
        assert all(set(s) == {"label", "grams", "default"} for s in row["servings"])
        assert sum(s["default"] for s in row["servings"]) == 1
