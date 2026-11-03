import pytest
from catalog_foods import make_food

from src.application.food_names import clean_name, food_keys, miss_key, slugify


@pytest.mark.parametrize(
    ("raw", "name", "key"),
    [
        ("Egg (x3)", "Egg", "egg"),
        ("egg (X 12) ", "egg", "egg"),
        ("Bánh xèo!", "Bánh xèo", "banh xeo"),
        ("  Phở Đà ...  ", "Phở Đà", "pho da"),
        ("Cơm (tấm)", "Cơm (tấm)", "com (tam)"),  # only a count suffix is stripped
        (" (x2)", "", ""),
    ],
)
def test_clean_name_and_miss_key(raw, name, key):
    assert (clean_name(raw), miss_key(raw)) == (name, key)


def test_miss_key_is_capped_at_120_chars():
    assert len(miss_key("a" * 200)) == 120


def test_food_keys_cover_name_english_name_and_aliases():
    food = make_food(name="Bún chả", name_en="Grilled pork (x1)", aliases=["Bun Cha", "", "chả giò"])
    assert food_keys(food) == {"bun cha", "grilled pork", "cha gio"}
    assert food_keys(make_food(name_en=None, aliases=[])) == {"pho bo"}


@pytest.mark.parametrize(
    ("name", "slug"),
    [("Bún chả", "bun-cha"), ("  Đậu hũ -- sốt!  ", "dau-hu-sot"), ("!!!", "food"), ("a" * 100, "a" * 60), ("a" * 59 + " b", "a" * 59)],
)
def test_slugify(name, slug):
    assert slugify(name) == slug
