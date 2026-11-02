"""ground(): catalog numbers replace the model's for matched rows; unmatched rows keep theirs."""

from __future__ import annotations

import logging

from catalog_foods import make_food

from src.application.dtos.food_analysis import (
    FoodAnalysisDTO,
    IngredientSuggestionDTO,
    NutritionPer100gDTO,
)
from src.application.food_grounding import ground
from src.domain.enums import FoodSourceKind


def _row(catalog_food_id: str | None, grams: float = 550.0) -> IngredientSuggestionDTO:
    return IngredientSuggestionDTO(
        name="model name", quantity_g=grams, kcal=999, carbs_g=9.0, protein_g=8.0, fat_g=7.0,
        fiber_g=6.0, confidence=0.7, catalog_food_id=catalog_food_id,
    )


def _ground(*rows: IngredientSuggestionDTO, foods=None) -> list[IngredientSuggestionDTO]:
    foods = foods if foods is not None else [make_food()]
    result = FoodAnalysisDTO("Meal", list(rows), image_url=None)
    return ground(result, {f.slug: f for f in foods}).ingredients


def test_matched_row_is_computed_from_the_catalog():
    (row,) = _ground(_row("pho-bo"))

    assert (row.kcal, row.carbs_g, row.protein_g, row.fat_g, row.fiber_g) == (
        446, 56.1, 24.8, 13.2, 1.1,
    )
    assert row.catalog_food_id == "pho-bo"
    assert row.catalog_name == "Phở bò"
    assert row.verified is True
    assert row.source_ref == "nin:1"
    assert row.per100g == NutritionPer100gDTO(81, 10.2, 4.5, 2.4, 0.2)


def test_name_quantity_and_confidence_stay_the_models():
    (row,) = _ground(_row("pho-bo"))

    assert (row.name, row.quantity_g, row.confidence) == ("model name", 550.0, 0.7)


def test_rounding_is_half_up_not_bankers():
    (row,) = _ground(_row("pho-bo", grams=50.0))  # 81 * 50 / 100 = 40.5

    assert row.kcal == 41


def test_fiber_stays_none_when_the_food_has_no_fiber_value():
    (row,) = _ground(_row("pho-bo"), foods=[make_food(fiber_g=None)])

    assert row.fiber_g is None
    assert row.per100g.fiber_g is None


def test_unknown_slug_keeps_model_numbers_and_leaks_nothing():
    (row,) = _ground(_row("made-up-slug"))

    assert (row.kcal, row.carbs_g, row.fiber_g) == (999, 9.0, 6.0)
    assert (row.catalog_food_id, row.catalog_name, row.source_ref, row.per100g) == (None,) * 4
    assert row.verified is False


def test_null_id_is_unmatched():
    (row,) = _ground(_row(None))

    assert row.kcal == 999 and row.catalog_food_id is None and row.per100g is None


def test_legacy_food_is_unverified_but_numbers_still_come_from_the_catalog():
    legacy = make_food(source_kind=FoodSourceKind.LEGACY, source_ref=None)

    (row,) = _ground(_row("pho-bo"), foods=[legacy])

    assert row.verified is False and row.source_ref is None
    assert row.kcal == 446


def test_logs_each_match_and_the_totals(caplog):
    with caplog.at_level(logging.INFO, logger="foodfenbe.food_analysis"):
        _ground(_row("pho-bo"), _row("nope"), _row(None))

    assert "pho-bo" in caplog.text and "model kcal=999" in caplog.text
    assert "matched=1 unmatched=2" in caplog.text
