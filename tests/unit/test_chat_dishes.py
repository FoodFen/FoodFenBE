"""chat_dishes: DISHES section, marker stripper, card id validation. Pure, no fakes."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from src.application import chat_dishes
from src.application.chat_dishes import MAX_CARDS, MarkerStripper, pick_candidates, render_dishes, valid_ids
from src.application.dish_fit import Remaining, rank_dishes
from src.domain.entities.dish import Dish
from src.domain.entities.restaurant import Restaurant
from src.domain.enums import DietType, DishDiet

_ID = UUID(int=7)
_MARKER = f"[[dish:{_ID}]]"


def _strip(*deltas: str) -> tuple[str, list[UUID]]:
    s = MarkerStripper()
    out = "".join(s.feed(d) for d in deltas) + s.finish()
    return out, s.ids


def test_marker_inside_one_delta_is_removed_and_collected():
    assert _strip(f"Phở bò {_MARKER} ngon") == ("Phở bò  ngon", [_ID])


def test_marker_split_across_deltas_never_leaks():
    text = f"Try this {_MARKER}!"
    for cut in range(1, len(text)):
        assert _strip(text[:cut], text[cut:]) == ("Try this !", [_ID]), cut


def test_marker_fed_char_by_char():
    assert _strip(*f"a{_MARKER}b") == ("ab", [_ID])


def test_double_bracket_that_is_not_a_marker_is_kept():
    assert _strip("see [[note]] and [x] ok") == ("see [[note]] and [x] ok", [])


def test_dish_prefix_with_a_non_uuid_is_kept():
    assert _strip("[[dish:not-a-uuid]] x") == ("[[dish:not-a-uuid]] x", [])
    assert _strip("[[dish:", "nope]]") == ("[[dish:nope]]", [])


def test_unclosed_marker_at_end_of_stream_is_flushed_as_text():
    assert _strip("hi [[dish:0000") == ("hi [[dish:0000", [])
    assert _strip("hi [") == ("hi [", [])


def test_held_text_is_not_emitted_until_it_can_no_longer_be_a_marker():
    s = MarkerStripper()
    assert s.feed("a [[dish:00000000") == "a "
    assert s.feed("x") == "[[dish:00000000x"


def test_several_markers_keep_order():
    other = UUID(int=9)
    assert _strip(f"[[dish:{other}]]{_MARKER}")[1] == [other, _ID]


def test_valid_ids_keeps_candidates_dedupes_in_order_and_caps():
    ids = [UUID(int=i) for i in range(1, 10)]
    assert valid_ids([ids[2], ids[0], ids[2], UUID(int=99)], set(ids)) == [ids[2], ids[0]]
    assert len(valid_ids(ids, set(ids))) == MAX_CARDS == 5


def _dish(name: str, kcal: int, diet: DishDiet = DishDiet.NONE, **macros) -> tuple[Dish, Restaurant]:
    r = Restaurant.create(
        user_id=1, name="Quán A", address="a", phone="1", opening_hours="x", latitude=1.0, longitude=2.0
    )
    d = Dish.create(
        restaurant_id=r.id, name=name, price=Decimal(55000), serving_g=300, kcal=kcal,
        protein_g=macros.get("p", 10), carbs_g=macros.get("c", 20), fat_g=macros.get("f", 5), diet_tag=diet,
    )
    return d, r


def _public(*pairs):
    return {d.id: (d, r) for d, r in pairs}


def test_section_lists_one_line_per_dish_with_suggested_flag_and_reasons():
    fits, over = _dish("Phở", 400), _dish("Bún", 600)
    pairs = [fits, over]
    ranked = rank_dishes([d for d, _ in pairs], Remaining(kcal=500, protein_g=50, carbs_g=60, fat_g=20), None)
    text = render_dishes(pick_candidates(ranked, None), _public(*pairs))

    assert text.startswith("DISHES")
    assert "[[dish:<id>]]" in text  # the instruction travels with the section
    line = next(ln for ln in text.splitlines() if str(fits[0].id) in ln)
    assert "Phở" in line and "Quán A" in line and "400" in line and "55000" in line
    assert "not suggested" not in line and "suggested" in line
    # top-up suggests the least-over dishes with their warning
    assert "exceeds_kcal" in next(ln for ln in text.splitlines() if str(over[0].id) in ln)


def test_no_goal_lists_dishes_none_suggested():
    pair = _dish("Phở", 400)
    ranked = rank_dishes([pair[0]], None, None)
    text = render_dishes(pick_candidates(ranked, None), _public(pair))
    assert str(pair[0].id) in text and "not suggested" in text


def test_header_scopes_list_to_restaurant_picks():
    pair = _dish("Phở", 400)
    text = render_dishes(pick_candidates(rank_dishes([pair[0]], None, None), None), _public(pair))
    for part in ("only when suggesting a dish to order", "FoodFen doesn't have it yet", "comes first"):
        assert part in text


def test_diet_incompatible_dishes_are_dropped():
    meat, veg = _dish("Thịt", 400), _dish("Chay", 400, DishDiet.VEGAN)
    ranked = rank_dishes([meat[0], veg[0]], None, DietType.VEGAN)
    cands = pick_candidates(ranked, DietType.VEGAN)
    assert [c.dish.id for c in cands] == [veg[0].id]
    assert str(meat[0].id) not in render_dishes(cands, _public(meat, veg))


def test_section_is_omitted_without_diet_ok_dish():
    meat = _dish("Thịt", 400)
    assert pick_candidates(rank_dishes([meat[0]], None, DietType.VEGAN), DietType.VEGAN) == []
    assert render_dishes([], {}) == ""


def test_candidates_are_capped(monkeypatch):
    monkeypatch.setattr(chat_dishes, "MAX_CHAT_DISHES", 2)
    pairs = [_dish(f"d{i}", 100 + i) for i in range(5)]
    ranked = rank_dishes([d for d, _ in pairs], None, None)
    assert len(pick_candidates(ranked, None)) == 2
