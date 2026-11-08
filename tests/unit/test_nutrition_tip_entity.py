from datetime import timedelta

import pytest

from src.domain.entities.nutrition_tip import NutritionTip
from src.domain.exceptions import InvalidNutritionTipException


def test_create_trims_and_defaults():
    tip = NutritionTip.create("  Uống nước  ", " Drink water ")

    assert (tip.text_vi, tip.text_en, tip.is_active) == ("Uống nước", "Drink water", True)
    assert tip.created_at == tip.updated_at


@pytest.mark.parametrize("vi, en, field", [("   ", "ok", "text_vi"), ("ok", "", "text_en")])
def test_empty_after_trim_is_text_required(vi, en, field):
    with pytest.raises(InvalidNutritionTipException) as exc:
        NutritionTip.create(vi, en)
    assert (exc.value.code, exc.value.field) == ("text_required", field)


def test_300_chars_ok_301_too_long():
    NutritionTip.create("a" * 300, "b" * 300)

    with pytest.raises(InvalidNutritionTipException) as exc:
        NutritionTip.create("a", "b" * 301)
    assert (exc.value.code, exc.value.field) == ("text_too_long", "text_en")


def test_update_changes_only_given_fields_and_bumps_updated_at():
    tip = NutritionTip.create("vi", "en")
    tip.updated_at -= timedelta(days=1)
    before = tip.updated_at

    tip.update(text_en="  new  ", is_active=False)

    assert (tip.text_vi, tip.text_en, tip.is_active) == ("vi", "new", False)
    assert tip.updated_at > before


def test_invalid_update_changes_nothing():
    tip = NutritionTip.create("vi", "en")

    with pytest.raises(InvalidNutritionTipException):
        tip.update(text_vi=" ", is_active=False)

    assert (tip.text_vi, tip.is_active) == ("vi", True)
