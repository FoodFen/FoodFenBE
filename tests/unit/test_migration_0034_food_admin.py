import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("m0034", _ROOT / "alembic/versions/0034_food_admin.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_BY_SLUG = dict(_mod._backfill())
_NAME = {f["id"]: f["name"] for f in json.loads((_ROOT / "alembic/data/foods.json").read_text(encoding="utf-8"))}


def test_backfill_covers_654_of_670_seed_foods():
    assert (len(_BY_SLUG), len(_NAME)) == (654, 670)


def test_backfill_takes_the_first_ascii_alias_that_adds_a_word():
    # "Thịt heo ba chỉ" has the alias "thit ba chi": only Vietnamese words, so skipped for an English one.
    slug = next(s for s, n in _NAME.items() if n == "Thịt heo ba chỉ")
    assert _BY_SLUG[slug].isascii() and _BY_SLUG[slug] != "thit ba chi"
    assert _mod._words("Bún chả") >= _mod._words("bun cha")


def test_backfill_leaves_foods_without_a_new_english_word_null():
    missing = {n for s, n in _NAME.items() if s not in _BY_SLUG}
    assert {"Pizza", "Hotdog", "Kiwi", "Granola"} <= missing
    assert all(en.isascii() for en in _BY_SLUG.values())
