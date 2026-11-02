"""Grounding: replace the model's invented nutrition with catalog numbers for matched rows."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import replace

from src.application.dtos.food_analysis import (
    FoodAnalysisDTO,
    IngredientSuggestionDTO,
    NutritionPer100gDTO,
)
from src.domain.entities.catalog_food import CatalogFood

_log = logging.getLogger("foodfenbe.food_analysis")


def _round_half_up(x: float, digits: int = 0) -> float:
    """Like JS Math.round (the app and the catalog build use it); Python's round is banker's."""
    scale = 10**digits
    return math.floor(x * scale + 0.5) / scale


def _ground_row(row: IngredientSuggestionDTO, food: CatalogFood) -> IngredientSuggestionDTO:
    g = row.quantity_g
    return replace(
        row,
        kcal=int(_round_half_up(food.kcal * g / 100)),
        carbs_g=_round_half_up(food.carbs_g * g / 100, 1),
        protein_g=_round_half_up(food.protein_g * g / 100, 1),
        fat_g=_round_half_up(food.fat_g * g / 100, 1),
        fiber_g=None if food.fiber_g is None else _round_half_up(food.fiber_g * g / 100, 1),
        catalog_food_id=food.slug,
        catalog_name=food.name,
        verified=food.verified,
        source_ref=food.source_ref,
        per100g=NutritionPer100gDTO(
            food.kcal, food.carbs_g, food.protein_g, food.fat_g, food.fiber_g
        ),
    )


def ground(result: FoodAnalysisDTO, catalog: Mapping[str, CatalogFood]) -> FoodAnalysisDTO:
    rows: list[IngredientSuggestionDTO] = []
    matched = 0
    for row in result.ingredients:
        food = catalog.get(row.catalog_food_id) if row.catalog_food_id is not None else None
        if food is None:  # an unknown slug must not leak through
            rows.append(
                replace(
                    row,
                    catalog_food_id=None,
                    catalog_name=None,
                    verified=False,
                    source_ref=None,
                    per100g=None,
                )
            )
            continue
        grounded = _ground_row(row, food)
        matched += 1
        _log.info(
            "grounded %s %sg: model kcal=%s c=%s p=%s f=%s -> catalog kcal=%s c=%s p=%s f=%s",
            food.slug,
            row.quantity_g,
            row.kcal,
            row.carbs_g,
            row.protein_g,
            row.fat_g,
            grounded.kcal,
            grounded.carbs_g,
            grounded.protein_g,
            grounded.fat_g,
        )
        rows.append(grounded)
    _log.info("matched=%d unmatched=%d", matched, len(rows) - matched)
    return replace(result, ingredients=rows)
