"""GET /foods: the public catalog the Mobile app syncs from (full dump or delta since a cursor)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest_asyncio

from src.domain.enums import FoodCategory, FoodSourceKind
from src.infrastructure.db.models.food_model import FoodORM
from src.infrastructure.db.session import SessionLocal

OLD = datetime(2026, 1, 1, tzinfo=UTC)
_SERVING = {"label": "1 bát", "grams": 300, "default": True}


async def _seed(slug, name, *, at=OLD, archived=False, kind=FoodSourceKind.NIN):
    async with SessionLocal() as session:
        session.add(FoodORM(
            id=uuid4(), slug=slug, name=name, name_en=f"{name} EN", aliases=["a1", "a2"],
            category=FoodCategory.MON_NUOC, source_kind=kind,
            source_ref=None if kind == FoodSourceKind.LEGACY else "nin:1", kcal=100, carbs_g=10.0, protein_g=5.0,
            fat_g=2.0, fiber_g=None, servings=[_SERVING], archived=archived, created_at=OLD, updated_at=at,
            updated_by_admin_id=None,
        ))
        await session.commit()


@pytest_asyncio.fixture
async def admin(make_user):
    headers, _ = await make_user("admin@example.com", admin=True)
    return headers


async def _slugs(client, since=None):
    resp = await client.get("/foods", params={"updatedSince": since} if since else None)
    assert resp.status_code == 200
    return [f["slug"] for f in resp.json()["foods"]]


async def test_full_list_is_public_includes_archived_and_has_the_wire_shape(client):
    await _seed("b", "B", archived=True, kind=FoodSourceKind.LEGACY)
    await _seed("a", "A")
    resp = await client.get("/foods")  # no auth header
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"foods", "serverTime"}
    assert [f["slug"] for f in body["foods"]] == ["a", "b"]
    assert body["foods"][0] == {
        "slug": "a", "name": "A", "nameEn": "A EN", "aliases": ["a1", "a2"], "category": "mon-nuoc",
        "sourceKind": "nin", "sourceRef": "nin:1", "verified": True,
        "per100g": {"kcal": 100, "carbsG": 10.0, "proteinG": 5.0, "fatG": 2.0, "fiberG": None},
        "servings": [_SERVING], "archived": False, "updatedAt": "2026-01-01T00:00:00Z",
    }
    assert (body["foods"][1]["archived"], body["foods"][1]["verified"], body["foods"][1]["sourceRef"]) == (True, False, None)


async def test_updated_since_is_inclusive(client):
    cursor = datetime(2026, 6, 1, 12, tzinfo=UTC)
    await _seed("before", "Before", at=cursor - timedelta(microseconds=1))
    await _seed("exact", "Exact", at=cursor)
    await _seed("after", "After", at=cursor + timedelta(seconds=1), archived=True)
    assert await _slugs(client, cursor.isoformat()) == ["after", "exact"]
    assert await _slugs(client, "2026-06-01T19:00:00+07:00") == ["after", "exact"]  # same instant, other offset
    assert await _slugs(client, (cursor + timedelta(seconds=2)).isoformat()) == []


async def test_server_time_is_taken_while_handling_the_request(client):
    t0 = datetime.now(UTC)
    body = (await client.get("/foods")).json()
    t1 = datetime.now(UTC)
    assert t0 <= datetime.fromisoformat(body["serverTime"]) <= t1


async def test_a_malformed_updated_since_is_422(client):
    for bad in ("nope", "2026-13-45T00:00:00Z", "", "2026-06-01T12:00:00"):  # last: no offset
        resp = await client.get("/foods", params={"updatedSince": bad})
        assert resp.status_code == 422, bad


async def test_an_edit_archive_and_unarchive_each_reach_the_next_delta(client, admin):
    await _seed("pho", "Phở")
    await _seed("bun", "Bún")
    cursor = (await client.get("/foods")).json()["serverTime"]
    assert await _slugs(client, cursor) == []

    assert (await client.patch("/admin/foods/pho", json={"kcal": 120}, headers=admin)).status_code == 200
    delta = (await client.get("/foods", params={"updatedSince": cursor})).json()
    assert [(f["slug"], f["per100g"]["kcal"]) for f in delta["foods"]] == [("pho", 120)]

    cursor = delta["serverTime"]
    assert (await client.post("/admin/foods/bun/archive", headers=admin)).status_code == 200
    delta = (await client.get("/foods", params={"updatedSince": cursor})).json()
    assert [(f["slug"], f["archived"]) for f in delta["foods"]] == [("bun", True)]

    cursor = delta["serverTime"]
    assert (await client.post("/admin/foods/bun/unarchive", headers=admin)).status_code == 200
    delta = (await client.get("/foods", params={"updatedSince": cursor})).json()
    assert [(f["slug"], f["archived"]) for f in delta["foods"]] == [("bun", False)]


async def test_archive_and_unarchive_bump_updated_at(client, admin):
    await _seed("bun", "Bún")  # updated_at is 2026-01-01
    for path, archived in (("archive", True), ("unarchive", False)):
        before = (await client.get("/foods")).json()["foods"][0]["updatedAt"]
        assert (await client.post(f"/admin/foods/bun/{path}", headers=admin)).status_code == 200
        food = (await client.get("/foods")).json()["foods"][0]
        assert food["archived"] is archived and food["updatedAt"] > before
