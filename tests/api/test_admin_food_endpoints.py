"""Admin food catalog: list / read / create / edit / archive, the change log, and the AI's unmatched names."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from src.application.dtos.food_analysis import IngredientSuggestionDTO
from src.domain.enums import FoodCategory, FoodSourceKind
from src.infrastructure.db.models.food_model import FoodORM
from src.infrastructure.db.repositories.food_miss_repository import SQLAlchemyFoodMissRepository
from src.infrastructure.db.session import SessionLocal

T0 = datetime(2026, 11, 3, 8, tzinfo=UTC)
_SERVING = {"label": "1 bát", "grams": 300, "default": True}


@pytest_asyncio.fixture
async def admin(make_user):
    headers, _ = await make_user("admin@example.com", admin=True)
    return headers


async def _seed(slug, name, *, aliases=(), name_en=None, category=FoodCategory.MON_NUOC, kind=FoodSourceKind.NIN,
                kcal=100, archived=False):
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        session.add(FoodORM(
            id=uuid4(), slug=slug, name=name, name_en=name_en, aliases=list(aliases), category=category,
            source_kind=kind, source_ref=None if kind == FoodSourceKind.LEGACY else "nin:1", kcal=kcal,
            carbs_g=10.0, protein_g=5.0, fat_g=2.0, fiber_g=1.0, servings=[_SERVING], archived=archived,
            created_at=now, updated_at=now, updated_by_admin_id=None,
        ))
        await session.commit()


async def _record(*pairs, language="vi", at=T0):
    async with SessionLocal() as session:
        await SQLAlchemyFoodMissRepository(session).record(list(pairs), language, at)
        await session.commit()


def _body(**over):
    return {
        "name": "Bún chả", "nameEn": "Grilled pork with noodles", "aliases": ["bun cha"], "category": "bun-tron",
        "kcal": 180, "carbsG": 20, "proteinG": 9, "fatG": 7, "fiberG": 1.5, "servings": [_SERVING], **over,
    }


async def _miss_id(client, admin, key):
    misses = (await client.get("/admin/food-misses", headers=admin)).json()["misses"]
    return next(m["id"] for m in misses if m["key"] == key)


async def _create(client, admin, **over):
    return await client.post("/admin/foods", json=_body(**over), headers=admin)


async def _changes(client, admin, slug):
    return (await client.get(f"/admin/foods/{slug}/changes", headers=admin)).json()


# --- list ---


async def test_list_search_ignores_accents_case_and_d_stroke(client, admin):
    await _seed("bun-cha", "Bún chả")
    await _seed("dau-hu", "Đậu hũ", aliases=["tofu"])
    await _seed("com", "Cơm", name_en="Steamed rice")

    def names(resp):
        return [f["name"] for f in resp.json()["foods"]]

    assert names(await client.get("/admin/foods?q=bun cha", headers=admin)) == ["Bún chả"]
    assert names(await client.get("/admin/foods?q=DAU HU", headers=admin)) == ["Đậu hũ"]
    assert names(await client.get("/admin/foods?q=đậu", headers=admin)) == ["Đậu hũ"]
    assert names(await client.get("/admin/foods?q=tofu", headers=admin)) == ["Đậu hũ"]  # alias
    assert names(await client.get("/admin/foods?q=steamed", headers=admin)) == ["Cơm"]  # English name
    assert names(await client.get("/admin/foods?q=dau-hu", headers=admin)) == ["Đậu hũ"]  # slug
    assert names(await client.get("/admin/foods?q=zzz", headers=admin)) == []


async def test_list_row_shape_sorted_by_folded_name(client, admin):
    await _seed("e", "Ếch", kind=FoodSourceKind.LEGACY)
    await _seed("d", "Dưa")
    await _seed("a", "Ăn vặt", name_en="Snack")
    body = (await client.get("/admin/foods", headers=admin)).json()
    assert [f["slug"] for f in body["foods"]] == ["a", "d", "e"]  # an vat, dua, ech
    assert (body["total"], body["nextCursor"]) == (3, None)
    row = body["foods"][0]
    assert set(row) == {
        "slug", "name", "nameEn", "category", "sourceKind", "sourceRef", "verified", "kcal", "carbsG", "proteinG",
        "fatG", "fiberG", "archived", "updatedAt",
    }
    assert (row["nameEn"], row["sourceKind"], row["sourceRef"], row["verified"]) == ("Snack", "nin", "nin:1", True)
    assert body["foods"][2]["verified"] is False and body["foods"][2]["sourceRef"] is None


async def test_list_filters_and_paging(client, admin):
    await _seed("a", "A", category=FoodCategory.COM)
    await _seed("b", "B", kind=FoodSourceKind.LEGACY)
    await _seed("c", "C")
    await _seed("d", "D", archived=True)

    def slugs(resp):
        return [f["slug"] for f in resp.json()["foods"]]

    assert slugs(await client.get("/admin/foods?category=com", headers=admin)) == ["a"]
    assert slugs(await client.get("/admin/foods?verified=false", headers=admin)) == ["b"]
    assert slugs(await client.get("/admin/foods?verified=true", headers=admin)) == ["a", "c"]
    assert slugs(await client.get("/admin/foods?archived=true", headers=admin)) == ["d"]
    first = (await client.get("/admin/foods?limit=2", headers=admin)).json()
    assert ([f["slug"] for f in first["foods"]], first["total"], first["nextCursor"]) == (["a", "b"], 3, "2")
    second = (await client.get("/admin/foods?limit=2&cursor=2", headers=admin)).json()
    assert ([f["slug"] for f in second["foods"]], second["nextCursor"]) == (["c"], None)
    assert (await client.get("/admin/foods?limit=51", headers=admin)).status_code == 422
    assert (await client.get("/admin/foods?cursor=x", headers=admin)).status_code == 422


async def test_get_detail_and_404(client, admin):
    created = (await _create(client, admin)).json()
    got = (await client.get("/admin/foods/bun-cha", headers=admin)).json()
    assert got == created
    assert got["aliases"] == ["bun cha"] and got["servings"] == [_SERVING]
    assert got["updatedByEmail"] == "admin@example.com" and "createdAt" in got
    assert (await client.get("/admin/foods/nope", headers=admin)).status_code == 404


# --- create ---


async def test_create_is_a_verified_team_food_with_a_slug_from_the_name(client, admin):
    resp = await _create(client, admin, name="  Đậu hũ sốt cà  ", nameEn=None)
    assert resp.status_code == 201
    body = resp.json()
    assert (body["slug"], body["name"], body["nameEn"]) == ("dau-hu-sot-ca", "Đậu hũ sốt cà", None)
    assert (body["sourceKind"], body["sourceRef"], body["verified"], body["archived"]) == ("team", "team", True, False)
    assert (body["kcal"], body["fiberG"]) == (180, 1.5)
    assert (await client.get("/admin/foods/dau-hu-sot-ca", headers=admin)).status_code == 200


async def test_create_clashing_slug_gets_a_numeric_suffix(client, admin):
    assert (await _create(client, admin, name="Bún chả")).json()["slug"] == "bun-cha"
    second = await _create(client, admin, name="Bún, chả!")  # a different name, the same slug
    assert second.status_code == 201 and second.json()["slug"] == "bun-cha-2"
    assert (await _create(client, admin, name="Bún - chả")).json()["slug"] == "bun-cha-3"


async def test_create_duplicate_folded_name_is_409_even_if_archived(client, admin):
    await _create(client, admin)
    for name in ("BUN CHA", "bún chả"):
        resp = await _create(client, admin, name=name)
        assert resp.status_code == 409 and resp.json()["error"] == "food_name_taken"
    assert (await client.post("/admin/foods/bun-cha/archive", headers=admin)).status_code == 200
    assert (await _create(client, admin, name="Bun Cha")).status_code == 409


async def test_create_validation_is_422(client, admin):
    bad = [
        {"name": "  "}, {"name": "x" * 121}, {"nameEn": "x" * 121}, {"aliases": ["x" * 81]},
        {"aliases": [f"a{i}" for i in range(21)]}, {"kcal": 901}, {"kcal": -1}, {"carbsG": 101}, {"fatG": -1},
        {"carbsG": 60, "proteinG": 30, "fatG": 20}, {"fiberG": 101}, {"category": "nope"}, {"servings": []},
        {"servings": [{**_SERVING, "grams": 0}]}, {"servings": [{**_SERVING, "grams": 5001}]},
        {"servings": [{**_SERVING, "label": ""}]},
        {"servings": [_SERVING, {"label": "b", "grams": 5, "default": True}]},  # two defaults
        {"servings": [{**_SERVING, "default": False}]},  # none
        {"servings": [{"label": f"s{i}", "grams": 5, "default": i == 0} for i in range(11)]},
    ]
    for over in bad:
        resp = await _create(client, admin, **over)
        assert resp.status_code == 422, over
    assert (await client.post("/admin/foods", json={"name": "x"}, headers=admin)).status_code == 422
    assert (await client.get("/admin/foods", headers=admin)).json()["total"] == 0


_BAD_SERVING = {"label": "b", "grams": 5, "default": False}
_RULE_CODES = [  # every catalog rule: the request override, the code and the camelCase field the Web translates
    ({"name": "  "}, "name_required", "name"),
    ({"name": "x" * 121}, "name_too_long", "name"),
    ({"nameEn": "x" * 121}, "name_en_too_long", "nameEn"),
    ({"aliases": [f"a{i}" for i in range(21)]}, "too_many_aliases", "aliases"),
    ({"aliases": ["x" * 81]}, "alias_too_long", "aliases"),
    ({"kcal": 901}, "kcal_out_of_range", "kcal"),
    ({"kcal": -1}, "kcal_out_of_range", "kcal"),
    ({"carbsG": 101}, "macro_out_of_range", "carbsG"),
    ({"proteinG": -1}, "macro_out_of_range", "proteinG"),
    ({"fatG": 101}, "macro_out_of_range", "fatG"),
    ({"carbsG": 60, "proteinG": 30, "fatG": 20}, "macros_sum_over_100", None),
    ({"fiberG": 101}, "fiber_out_of_range", "fiberG"),
    ({"servings": []}, "servings_count_out_of_range", "servings"),
    ({"servings": [{"label": f"s{i}", "grams": 5, "default": i == 0} for i in range(11)]},
     "servings_count_out_of_range", "servings"),
    ({"servings": [_SERVING, {**_BAD_SERVING, "label": " "}]}, "serving_label_out_of_range", "servings.1.label"),
    ({"servings": [{**_SERVING, "grams": 0}]}, "serving_grams_out_of_range", "servings.0.grams"),
    ({"servings": [_SERVING, {**_BAD_SERVING, "grams": 5001}]}, "serving_grams_out_of_range", "servings.1.grams"),
    ({"servings": [{**_SERVING, "default": False}]}, "servings_need_one_default", "servings"),
    ({"servings": [_SERVING, {**_BAD_SERVING, "default": True}]}, "servings_need_one_default", "servings"),
]


@pytest.mark.parametrize("over, code, field", _RULE_CODES)
async def test_catalog_rule_violations_carry_code_and_field(client, admin, over, code, field):
    body = (await _create(client, admin, **over)).json()
    assert body["code"] == code and body.get("field") == field
    assert body["message"]
    await _create(client, admin)  # the patch needs a food
    patched = await client.patch("/admin/foods/bun-cha", json=over, headers=admin)
    assert patched.status_code == 422 and patched.json()["code"] == code and patched.json().get("field") == field


async def test_catalog_rule_violation_status_is_422(client, admin):
    resp = await _create(client, admin, kcal=901)
    assert resp.status_code == 422
    assert resp.json() == {"message": "kcal must be from 0 to 900, got 901", "code": "kcal_out_of_range", "field": "kcal"}


async def test_create_cleans_aliases_and_drops_duplicates(client, admin):
    body = (await _create(client, admin, aliases=[" a ", "", "a", "A", "b"])).json()
    assert body["aliases"] == ["a", "A", "b"]


async def test_create_with_miss_id_resolves_that_miss(client, admin):
    await _record(("canh chua", "Canh chua"), ("other", "Other"))
    miss_id = await _miss_id(client, admin, "canh chua")
    # a name that is not the miss key: only missId links them
    resp = await _create(client, admin, name="Canh chua cá", aliases=[], nameEn=None, missId=miss_id)
    assert resp.status_code == 201
    assert [m["key"] for m in (await client.get("/admin/food-misses", headers=admin)).json()["misses"]] == ["other"]
    resolved = (await client.get("/admin/food-misses?status=resolved", headers=admin)).json()["misses"]
    assert [(m["key"], m["status"]) for m in resolved] == [("canh chua", "resolved")]


async def test_create_ignores_an_unknown_or_ignored_miss_id(client, admin):
    await _record(("canh chua", "Canh chua"))
    miss_id = await _miss_id(client, admin, "canh chua")
    await client.post(f"/admin/food-misses/{miss_id}/ignore", headers=admin)
    assert (await _create(client, admin, name="Canh A", missId=miss_id)).status_code == 201
    assert (await _create(client, admin, name="Canh B", missId=str(uuid4()))).status_code == 201
    assert (await client.get("/admin/food-misses?status=ignored", headers=admin)).json()["total"] == 1
    assert (await client.get("/admin/food-misses?status=resolved", headers=admin)).json()["total"] == 0


async def test_create_auto_resolves_open_misses_matching_name_english_name_or_alias(client, admin):
    await _record(("grilled pork with noodles", "Grilled pork with noodles"), ("bun cha ha noi", "Bún chả Hà Nội"),
                  ("bun cha", "bun cha"), ("unrelated", "Unrelated"))
    await _create(client, admin, aliases=["bún chả hà nội"])  # name "Bún chả" -> key "bun cha"
    left = (await client.get("/admin/food-misses", headers=admin)).json()["misses"]
    assert [m["key"] for m in left] == ["unrelated"]


# --- edit ---


async def test_patch_numbers_switch_the_source_to_team_even_for_a_legacy_food(client, admin):
    await _seed("yakult", "Yakult", kind=FoodSourceKind.LEGACY, kcal=70)
    resp = await client.patch("/admin/foods/yakult", json={"kcal": 72}, headers=admin)
    assert resp.status_code == 200
    body = resp.json()
    assert (body["kcal"], body["sourceKind"], body["sourceRef"], body["verified"]) == (72, "team", "team", True)
    assert body["updatedByEmail"] == "admin@example.com"
    [change] = await _changes(client, admin, "yakult")
    assert (change["before"]["sourceKind"], change["before"]["sourceRef"]) == ("legacy", None)
    assert (change["after"]["sourceKind"], change["after"]["kcal"]) == ("team", 72)


async def test_patch_each_number_field_switches_a_sourced_food_to_team(client, admin):
    for i, over in enumerate([{"carbsG": 11}, {"proteinG": 6}, {"fatG": 3}, {"fiberG": 2}, {"fiberG": None}]):
        await _seed(f"f{i}", f"F{i}")
        body = (await client.patch(f"/admin/foods/f{i}", json=over, headers=admin)).json()
        assert (body["sourceKind"], body["sourceRef"]) == ("team", "team"), over


async def test_patch_without_number_changes_keeps_the_source(client, admin):
    await _seed("yakult", "Yakult", kind=FoodSourceKind.LEGACY)
    await _seed("pho", "Phở")
    body = (await client.patch(
        "/admin/foods/yakult",
        json={"name": "Yakult Light", "nameEn": "Yakult", "aliases": ["ya"], "category": "do-uong", "kcal": 100,
              "servings": [{"label": "chai", "grams": 65, "default": True}]},
        headers=admin,
    )).json()
    assert (body["name"], body["sourceKind"], body["sourceRef"], body["verified"]) == ("Yakult Light", "legacy", None, False)
    assert (body["nameEn"], body["category"], body["servings"][0]["label"]) == ("Yakult", "do-uong", "chai")
    assert (await client.patch("/admin/foods/pho", json={"name": "Phở bò"}, headers=admin)).json()["sourceKind"] == "nin"


async def test_patch_is_partial_and_slug_never_changes(client, admin):
    await _create(client, admin)
    body = (await client.patch("/admin/foods/bun-cha", json={"name": "Bún chả Hà Nội"}, headers=admin)).json()
    assert (body["slug"], body["name"], body["kcal"], body["aliases"]) == ("bun-cha", "Bún chả Hà Nội", 180, ["bun cha"])


async def test_patch_that_changes_nothing_writes_no_change_row(client, admin):
    await _create(client, admin)
    before = (await client.get("/admin/foods/bun-cha", headers=admin)).json()
    for patch in ({}, {"kcal": 180}, {"name": " Bún chả ", "aliases": ["bun cha", "bun cha"]}, {"name": None}):
        resp = await client.patch("/admin/foods/bun-cha", json=patch, headers=admin)
        assert resp.status_code == 200 and resp.json() == before, patch
    assert [c["action"] for c in await _changes(client, admin, "bun-cha")] == ["create"]


async def test_patch_fiber_null_clears_and_zero_is_kept(client, admin):
    await _create(client, admin)
    assert (await client.patch("/admin/foods/bun-cha", json={"fiberG": 0}, headers=admin)).json()["fiberG"] == 0
    assert (await client.patch("/admin/foods/bun-cha", json={"fiberG": None}, headers=admin)).json()["fiberG"] is None
    assert (await client.patch("/admin/foods/bun-cha", json={"nameEn": None}, headers=admin)).json()["nameEn"] is None
    assert len(await _changes(client, admin, "bun-cha")) == 4


async def test_patch_errors(client, admin):
    await _create(client, admin)
    await _create(client, admin, name="Phở")
    assert (await client.patch("/admin/foods/nope", json={"kcal": 1}, headers=admin)).status_code == 404
    clash = await client.patch("/admin/foods/pho", json={"name": "BUN CHA"}, headers=admin)
    assert clash.status_code == 409 and clash.json()["error"] == "food_name_taken"
    assert (await client.patch("/admin/foods/pho", json={"name": "PHO"}, headers=admin)).status_code == 200  # itself
    for over in ({"kcal": 901}, {"name": " "}, {"carbsG": 100, "proteinG": 5}, {"servings": []}, {"category": "x"}):
        assert (await client.patch("/admin/foods/pho", json=over, headers=admin)).status_code == 422, over
    assert (await client.get("/admin/foods/pho", headers=admin)).json()["kcal"] == 180


async def test_patch_new_name_or_alias_resolves_open_misses_but_other_edits_do_not(client, admin):
    await _create(client, admin)
    await _record(("pizza", "Pizza"), ("banh my", "Bánh mì"))
    await client.patch("/admin/foods/bun-cha", json={"kcal": 190}, headers=admin)
    assert (await client.get("/admin/food-misses", headers=admin)).json()["total"] == 2
    await client.patch("/admin/foods/bun-cha", json={"aliases": ["bun cha", "PIZZA"]}, headers=admin)
    assert [m["key"] for m in (await client.get("/admin/food-misses", headers=admin)).json()["misses"]] == ["banh my"]


# --- archive ---


async def test_archive_and_unarchive_are_idempotent_one_change_row_per_flip(client, admin):
    await _create(client, admin)
    for _ in range(2):
        resp = await client.post("/admin/foods/bun-cha/archive", headers=admin)
        assert resp.status_code == 200 and resp.json()["archived"] is True
    assert (await client.get("/admin/foods", headers=admin)).json()["total"] == 0
    assert (await client.get("/admin/foods?archived=true", headers=admin)).json()["total"] == 1
    for _ in range(2):
        resp = await client.post("/admin/foods/bun-cha/unarchive", headers=admin)
        assert resp.status_code == 200 and resp.json()["archived"] is False
    assert [c["action"] for c in await _changes(client, admin, "bun-cha")] == ["unarchive", "archive", "create"]


async def test_archive_unknown_is_404(client, admin):
    assert (await client.post("/admin/foods/nope/archive", headers=admin)).status_code == 404
    assert (await client.post("/admin/foods/nope/unarchive", headers=admin)).status_code == 404


async def test_unarchive_conflicts_with_an_active_food_of_the_same_name(client, admin):
    await _seed("old", "Phở", archived=True)
    await _seed("new", "pho")
    resp = await client.post("/admin/foods/old/unarchive", headers=admin)
    assert resp.status_code == 409 and resp.json()["error"] == "food_name_taken"
    assert (await client.get("/admin/foods/old", headers=admin)).json()["archived"] is True


# --- change log ---


async def test_changes_newest_first_with_admin_email_and_camel_case_snapshots(client, admin):
    await _create(client, admin)
    await client.patch("/admin/foods/bun-cha", json={"kcal": 200}, headers=admin)
    await client.post("/admin/foods/bun-cha/archive", headers=admin)
    changes = await _changes(client, admin, "bun-cha")
    assert [c["action"] for c in changes] == ["archive", "update", "create"]
    assert {c["adminEmail"] for c in changes} == {"admin@example.com"}
    archive, update, create = changes
    assert create["before"] is None and create["after"]["kcal"] == 180
    assert (update["before"]["kcal"], update["after"]["kcal"]) == (180, 200)
    assert (archive["before"]["archived"], archive["after"]["archived"]) == (False, True)
    assert set(create["after"]) == {
        "name", "nameEn", "aliases", "category", "kcal", "carbsG", "proteinG", "fatG", "fiberG", "servings",
        "sourceKind", "sourceRef", "archived",
    }
    assert {"id", "createdAt"} <= set(create)
    assert (await client.get("/admin/foods/nope/changes", headers=admin)).status_code == 404


# --- unmatched names ---


async def test_misses_listed_by_count_then_recency_with_existing_food(client, admin):
    await _seed("pho-bo", "Phở bò", aliases=["pho"], name_en="Beef pho")
    await _seed("gone", "Gỏi", archived=True)
    await _record(("a", "A"), ("b", "B"), ("pho", "Pho"), ("goi", "Gỏi"), ("beef pho", "Beef pho"))
    await _record(("b", "B"), at=T0 + timedelta(hours=1))
    await _record(("a", "A"), at=T0 + timedelta(hours=2))
    await _record(("b", "B"), at=T0 + timedelta(hours=3))
    await _record(("a", "A"), at=T0 + timedelta(hours=4))
    body = (await client.get("/admin/food-misses", headers=admin)).json()
    assert [(m["key"], m["count"]) for m in body["misses"]][:2] == [("a", 3), ("b", 3)]  # a tie: the later sighting first
    assert body["total"] == 5 and body["nextCursor"] is None
    by_key = {m["key"]: m for m in body["misses"]}
    assert by_key["pho"]["existingFood"] == {"slug": "pho-bo", "name": "Phở bò"}  # alias
    assert by_key["beef pho"]["existingFood"] == {"slug": "pho-bo", "name": "Phở bò"}  # English name
    assert by_key["goi"]["existingFood"] is None  # the only match is archived
    assert by_key["a"]["existingFood"] is None
    assert set(by_key["a"]) == {"id", "key", "name", "language", "count", "firstSeenAt", "lastSeenAt", "status", "existingFood"}
    assert by_key["a"]["status"] == "open"


async def test_misses_page(client, admin):
    await _record(("a", "A"), ("b", "B"), ("c", "C"))
    first = (await client.get("/admin/food-misses?limit=2", headers=admin)).json()
    assert (len(first["misses"]), first["total"], first["nextCursor"]) == (2, 3, "2")
    second = (await client.get("/admin/food-misses?limit=2&cursor=2", headers=admin)).json()
    assert (len(second["misses"]), second["nextCursor"]) == (1, None)
    assert (await client.get("/admin/food-misses?status=nope", headers=admin)).status_code == 422


async def test_ignore_and_reopen_a_miss(client, admin):
    await _record(("a", "A"))
    miss_id = (await client.get("/admin/food-misses", headers=admin)).json()["misses"][0]["id"]
    for _ in range(2):  # idempotent
        resp = await client.post(f"/admin/food-misses/{miss_id}/ignore", headers=admin)
        assert resp.status_code == 200 and resp.json()["status"] == "ignored"
    assert (await client.get("/admin/food-misses", headers=admin)).json()["total"] == 0
    assert (await client.get("/admin/food-misses?status=ignored", headers=admin)).json()["total"] == 1
    await _record(("a", "A"))  # a sighting never re-opens it
    assert (await client.get("/admin/food-misses", headers=admin)).json()["total"] == 0
    resp = await client.post(f"/admin/food-misses/{miss_id}/reopen", headers=admin)
    assert resp.status_code == 200 and (resp.json()["status"], resp.json()["count"]) == ("open", 2)
    for action in ("ignore", "reopen"):
        assert (await client.post(f"/admin/food-misses/{uuid4()}/{action}", headers=admin)).status_code == 404


async def test_a_resolved_miss_can_be_reopened(client, admin):
    await _record(("bun cha", "Bún chả"))
    await _create(client, admin)  # auto-resolves
    resolved = (await client.get("/admin/food-misses?status=resolved", headers=admin)).json()["misses"]
    resp = await client.post(f"/admin/food-misses/{resolved[0]['id']}/reopen", headers=admin)
    assert resp.json()["status"] == "open" and resp.json()["existingFood"]["slug"] == "bun-cha"


async def test_the_ai_records_unmatched_names_and_never_who_asked(client, admin, signed_up, food_vision_provider):
    await _seed("pho-bo", "Phở bò")
    row = IngredientSuggestionDTO("Egg (x3)", 100.0, 1, 1.0, 1.0, 1.0, None, 0.5, None)
    matched = IngredientSuggestionDTO("pho", 100.0, 1, 1.0, 1.0, 1.0, None, 0.5, "pho-bo")
    food_vision_provider.result = food_vision_provider.result.__class__("Meal", [row, matched], None)
    user = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    for _ in range(2):
        assert (await client.post("/ai/food/analyze-text", json={"description": "x", "language": "en"}, headers=user)).status_code == 200
    [miss] = (await client.get("/admin/food-misses", headers=admin)).json()["misses"]
    assert (miss["key"], miss["name"], miss["language"], miss["count"]) == ("egg", "Egg", "en", 2)


# --- access ---


async def test_non_admins_are_refused(client, make_user):
    user, _ = await make_user("plain@example.com")
    for method, path in [
        ("get", "/admin/foods"), ("get", "/admin/foods/x"), ("post", "/admin/foods"), ("patch", "/admin/foods/x"),
        ("post", "/admin/foods/x/archive"), ("post", "/admin/foods/x/unarchive"), ("get", "/admin/foods/x/changes"),
        ("get", "/admin/food-misses"), ("post", f"/admin/food-misses/{uuid4()}/ignore"),
        ("post", f"/admin/food-misses/{uuid4()}/reopen"),
    ]:
        assert (await getattr(client, method)(path, headers=user)).status_code == 403, path
        assert (await getattr(client, method)(path)).status_code == 401, path


# --- an edit reaches the next analysis ---


async def test_an_edit_changes_the_next_ai_analysis_without_a_restart(client, admin, signed_up, food_vision_provider):
    await _seed("pho-bo", "Phở bò", kcal=81)
    row = IngredientSuggestionDTO("pho", 500.0, 999, 1.0, 1.0, 1.0, None, 0.8, "pho-bo")
    food_vision_provider.result = food_vision_provider.result.__class__("Pho", [row], None)
    user = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    async def analyze() -> int:
        resp = await client.post("/ai/food/analyze-text", json={"description": "pho"}, headers=user)
        return resp.json()["ingredients"][0]["kcal"]

    assert await analyze() == 405  # 81 per 100 g x 500 g; the catalog is now cached in the process
    assert (await client.patch("/admin/foods/pho-bo", json={"kcal": 100}, headers=admin)).status_code == 200
    assert await analyze() == 500
    assert (await client.post("/admin/foods/pho-bo/archive", headers=admin)).status_code == 200
    assert await analyze() == 999  # archived: no longer matched, the model's own estimate stays


async def test_the_cache_is_invalidated_after_the_commit_and_only_on_success(client, admin, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.infrastructure.di import get_food_catalog_cache

    await _seed("pho-bo", "Phở bò")
    events = []
    monkeypatch.setattr(get_food_catalog_cache(), "invalidate", lambda: events.append("invalidate"))
    commit = AsyncSession.commit

    async def recording_commit(self):
        events.append("commit")
        await commit(self)

    monkeypatch.setattr(AsyncSession, "commit", recording_commit)

    assert (await client.patch("/admin/foods/pho-bo", json={"kcal": 100}, headers=admin)).status_code == 200
    assert events == ["commit", "invalidate"]
    events.clear()
    assert (await client.patch("/admin/foods/pho-bo", json={"kcal": 9999}, headers=admin)).status_code == 422
    assert (await client.patch("/admin/foods/nope", json={"kcal": 1}, headers=admin)).status_code == 404
    assert "invalidate" not in events
