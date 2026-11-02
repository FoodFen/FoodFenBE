"""Admin mascot CRUD, server-side artwork on GET /mascots, and POST /admin/images."""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.enums import CoinReason
from src.infrastructure.db.models.coin_transaction_model import CoinTransactionORM
from src.infrastructure.db.models.mascot_model import MascotImageORM
from src.infrastructure.db.session import engine

_URL = "https://res.cloudinary.com/testcloud/image/upload/v1/{}.png"
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


def _img(name: str) -> str:
    return _URL.format(name)


@pytest_asyncio.fixture
async def admin(make_user):
    headers, _ = await make_user("admin@example.com", admin=True)
    return headers


async def _create(client, admin, mascot_id="mochi", **extra):
    body = {"id": mascot_id, "name": "Mochi", "coinCost": 300, **extra}
    return await client.post("/admin/mascots", json=body, headers=admin)


async def _credit(user_id: int, amount: int) -> None:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(CoinTransactionORM.from_domain(CoinTransaction.create(user_id, amount, CoinReason.ADJUSTMENT)))
        await session.commit()


async def test_list_starts_with_the_seeded_default(client, admin):
    listed = (await client.get("/admin/mascots", headers=admin)).json()
    assert listed == [
        {"id": "default", "name": "Fen", "coinCost": 0, "active": True, "images": {}, "bodyColor": None, "ownerCount": 0,
         "equippedCount": 1}
    ]  # the admin themself has the free mascot equipped


async def test_list_counts_owners_and_equipped(client, admin, make_user):
    await _create(client, admin, images={"idle": _img("idle")}, active=True)
    user, user_id = await make_user("buyer@example.com")
    await _credit(user_id, 500)
    assert (await client.post("/mascots/mochi/purchase", headers=user)).status_code == 200
    assert (await client.put("/mascots/equipped", json={"mascotId": "mochi"}, headers=user)).status_code == 200

    listed = {m["id"]: m for m in (await client.get("/admin/mascots", headers=admin)).json()}
    assert (listed["mochi"]["ownerCount"], listed["mochi"]["equippedCount"]) == (1, 1)
    assert (listed["default"]["ownerCount"], listed["default"]["equippedCount"]) == (0, 1)  # admin only


async def test_list_is_ordered_by_cost_then_id_and_includes_inactive(client, admin):
    await _create(client, admin, "zeta", coinCost=100)
    await _create(client, admin, "alpha", coinCost=100)
    await _create(client, admin, "cheap", coinCost=0)
    listed = (await client.get("/admin/mascots", headers=admin)).json()
    assert [m["id"] for m in listed] == ["cheap", "default", "alpha", "zeta"]
    assert not listed[2]["active"]


async def test_create_returns_201_and_defaults_to_an_inactive_draft(client, admin):
    resp = await _create(client, admin)
    assert resp.status_code == 201
    assert resp.json() == {
        "id": "mochi", "name": "Mochi", "coinCost": 300, "active": False,
        "images": {}, "bodyColor": None, "ownerCount": 0, "equippedCount": 0,
    }


async def test_create_with_images_and_active(client, admin):
    resp = await _create(client, admin, active=True, images={"idle": _img("i"), "happy": _img("h")})
    assert resp.status_code == 201
    assert resp.json()["images"] == {"idle": _img("i"), "happy": _img("h")}
    assert (await client.get("/admin/mascots", headers=admin)).json()[-1]["images"] == resp.json()["images"]


async def test_create_with_a_taken_id_is_409(client, admin):
    assert (await _create(client, admin)).status_code == 201
    resp = await _create(client, admin)
    assert resp.status_code == 409 and resp.json()["error"] == "mascot_id_taken"
    resp = await _create(client, admin, "default")
    assert resp.status_code == 409 and resp.json()["error"] == "mascot_id_taken"


async def test_create_active_without_an_idle_image_is_409(client, admin):
    resp = await _create(client, admin, active=True, images={"happy": _img("h")})
    assert resp.status_code == 409 and resp.json()["error"] == "mascot_missing_idle_image"
    assert [m["id"] for m in (await client.get("/admin/mascots", headers=admin)).json()] == ["default"]


async def test_create_with_a_hand_drawn_id_may_be_active_without_art(client, admin):
    assert (await _create(client, admin, "chili", active=True)).status_code == 201


async def test_create_validation_is_422(client, admin):
    bad = [
        {"id": "Bad Slug"}, {"id": ""}, {"id": "x" * 33}, {"name": ""}, {"name": "x" * 41},
        {"coinCost": -1}, {"coinCost": 1_000_001}, {"images": {"dancing": _img("d")}},
        {"images": {"idle": "https://evil.example/a.png"}}, {"images": {"idle": None}},
    ]
    for override in bad:
        body = {"id": "mochi", "name": "Mochi", "coinCost": 1, **override}
        resp = await client.post("/admin/mascots", json=body, headers=admin)
        assert resp.status_code == 422, override


async def test_whitespace_name_is_422_and_name_is_trimmed(client, admin):
    assert (await _create(client, admin, name="   ")).status_code == 422
    assert (await _create(client, admin, name="  Moo ")).json()["name"] == "Moo"


async def test_patch_updates_fields(client, admin):
    await _create(client, admin)
    resp = await client.patch("/admin/mascots/mochi", json={"name": "Moo", "coinCost": 450}, headers=admin)
    assert resp.status_code == 200
    assert (resp.json()["name"], resp.json()["coinCost"], resp.json()["active"]) == ("Moo", 450, False)


async def test_body_color_round_trips_through_create_list_and_the_public_catalogue(client, admin, make_user):
    resp = await _create(client, admin, bodyColor="#A1b2C3", active=True, images={"idle": _img("i")})
    assert resp.status_code == 201 and resp.json()["bodyColor"] == "#A1b2C3"
    await _create(client, admin, "plain", coinCost=100)
    admin_by_id = {m["id"]: m for m in (await client.get("/admin/mascots", headers=admin)).json()}
    assert (admin_by_id["mochi"]["bodyColor"], admin_by_id["plain"]["bodyColor"]) == ("#A1b2C3", None)
    user, _ = await make_user("u@example.com")
    public = {m["id"]: m for m in (await client.get("/mascots", headers=user)).json()["mascots"]}
    assert (public["mochi"]["bodyColor"], public["default"]["bodyColor"]) == ("#A1b2C3", None)


async def test_patch_body_color_absent_keeps_null_resets_value_sets(client, admin):
    await _create(client, admin, bodyColor="#112233")
    resp = await client.patch("/admin/mascots/mochi", json={"name": "Moo"}, headers=admin)
    assert resp.json()["bodyColor"] == "#112233"  # absent = unchanged
    resp = await client.patch("/admin/mascots/mochi", json={"bodyColor": "#ABCDEF"}, headers=admin)
    assert resp.json()["bodyColor"] == "#ABCDEF"
    resp = await client.patch("/admin/mascots/mochi", json={"bodyColor": None}, headers=admin)
    assert resp.status_code == 200 and resp.json()["bodyColor"] is None  # explicit null = reset
    assert (await client.get("/admin/mascots", headers=admin)).json()[-1]["bodyColor"] is None


async def test_bad_body_color_is_422_on_create_and_patch(client, admin):
    for bad in ("red", "#12345", "#GGGGGG", "123456"):
        assert (await _create(client, admin, bodyColor=bad)).status_code == 422
    await _create(client, admin)
    resp = await client.patch("/admin/mascots/mochi", json={"bodyColor": "red"}, headers=admin)
    assert resp.status_code == 422


async def test_patch_images_merge_set_remove_untouched(client, admin):
    await _create(client, admin, images={"idle": _img("i"), "happy": _img("h")})
    resp = await client.patch(
        "/admin/mascots/mochi", json={"images": {"happy": None, "eating": _img("e")}}, headers=admin
    )
    assert resp.status_code == 200
    assert resp.json()["images"] == {"idle": _img("i"), "eating": _img("e")}
    resp = await client.patch("/admin/mascots/mochi", json={"images": {"eating": _img("e2")}}, headers=admin)
    assert resp.json()["images"] == {"idle": _img("i"), "eating": _img("e2")}
    resp = await client.patch("/admin/mascots/mochi", json={"name": "Moo"}, headers=admin)  # absent: untouched
    assert resp.json()["images"] == {"idle": _img("i"), "eating": _img("e2")}
    async with async_sessionmaker(engine)() as session:  # a removed state leaves no row behind
        rows = (await session.scalars(select(MascotImageORM).where(MascotImageORM.mascot_id == "mochi"))).all()
    assert sorted(r.state for r in rows) == ["eating", "idle"]


async def test_patch_unknown_id_is_404(client, admin):
    resp = await client.patch("/admin/mascots/nope", json={"name": "x"}, headers=admin)
    assert resp.status_code == 404


async def test_patch_validation_is_422(client, admin):
    await _create(client, admin)
    for body in ({"name": ""}, {"coinCost": -5}, {"images": {"nope": _img("x")}}, {"images": {"idle": "http://x/y.png"}}):
        assert (await client.patch("/admin/mascots/mochi", json=body, headers=admin)).status_code == 422, body


async def test_default_is_locked(client, admin):
    for body in ({"active": False}, {"coinCost": 10}):
        resp = await client.patch("/admin/mascots/default", json=body, headers=admin)
        assert resp.status_code == 409 and resp.json()["error"] == "mascot_default_locked"
    assert (await client.patch("/admin/mascots/default", json={"name": "Fen!"}, headers=admin)).status_code == 200
    resp = await client.delete("/admin/mascots/default", headers=admin)
    assert resp.status_code == 409 and resp.json()["error"] == "mascot_default_locked"


async def test_activating_needs_an_idle_image(client, admin):
    await _create(client, admin)
    resp = await client.patch("/admin/mascots/mochi", json={"active": True}, headers=admin)
    assert resp.status_code == 409 and resp.json()["error"] == "mascot_missing_idle_image"
    resp = await client.patch(
        "/admin/mascots/mochi", json={"active": True, "images": {"idle": _img("i")}}, headers=admin
    )  # same request adds the art
    assert resp.status_code == 200 and resp.json()["active"] is True
    resp = await client.patch("/admin/mascots/mochi", json={"images": {"idle": None}}, headers=admin)
    assert resp.status_code == 409 and resp.json()["error"] == "mascot_missing_idle_image"
    assert (await client.patch("/admin/mascots/mochi", json={"active": False, "images": {"idle": None}}, headers=admin)).status_code == 200


async def test_delete_unused_mascot_is_204_and_takes_its_images(client, admin):
    await _create(client, admin, images={"idle": _img("i")})
    assert (await client.delete("/admin/mascots/mochi", headers=admin)).status_code == 204
    assert [m["id"] for m in (await client.get("/admin/mascots", headers=admin)).json()] == ["default"]
    async with async_sessionmaker(engine)() as session:
        assert (await session.scalars(select(MascotImageORM))).all() == []
    assert (await client.delete("/admin/mascots/mochi", headers=admin)).status_code == 404


async def test_delete_is_409_when_owned_or_equipped(client, admin, make_user):
    await _create(client, admin, "owned", images={"idle": _img("o")}, active=True)
    await _create(client, admin, "worn", coinCost=0, images={"idle": _img("w")}, active=True)
    user, user_id = await make_user("buyer@example.com")
    await _credit(user_id, 500)
    await client.post("/mascots/owned/purchase", headers=user)
    await client.put("/mascots/equipped", json={"mascotId": "worn"}, headers=user)

    for mascot_id in ("owned", "worn"):
        resp = await client.delete(f"/admin/mascots/{mascot_id}", headers=admin)
        assert resp.status_code == 409 and resp.json()["error"] == "mascot_in_use"
    assert {m["id"] for m in (await client.get("/admin/mascots", headers=admin)).json()} >= {"owned", "worn"}


async def test_public_list_carries_images_and_hides_inactive_mascots(client, admin, make_user):
    await _create(client, admin, images={"idle": _img("i"), "happy": _img("h")}, active=True)
    await _create(client, admin, "draft", coinCost=100)
    user, user_id = await make_user("u@example.com")
    body = (await client.get("/mascots", headers=user)).json()
    by_id = {m["id"]: m for m in body["mascots"]}
    assert by_id["mochi"]["images"] == {"idle": _img("i"), "happy": _img("h")}
    assert by_id["default"]["images"] == {}
    assert "draft" not in by_id

    await _credit(user_id, 1000)
    assert (await client.post("/mascots/draft/purchase", headers=user)).status_code == 404
    bought = await client.post("/mascots/mochi/purchase", headers=user)
    assert {m["id"]: m for m in bought.json()["mascots"]}["mochi"]["images"] == by_id["mochi"]["images"]


async def test_hiding_a_mascot_removes_it_from_the_public_list(client, admin, make_user):
    await _create(client, admin, images={"idle": _img("i")}, active=True)
    user, _ = await make_user("u@example.com")
    assert "mochi" in {m["id"] for m in (await client.get("/mascots", headers=user)).json()["mascots"]}
    await client.patch("/admin/mascots/mochi", json={"active": False}, headers=admin)
    assert "mochi" not in {m["id"] for m in (await client.get("/mascots", headers=user)).json()["mascots"]}


async def test_non_admin_is_403_and_anonymous_401(client, make_user):
    plain, _ = await make_user("plain@example.com")
    calls = [
        client.get("/admin/mascots", headers=plain),
        client.post("/admin/mascots", json={"id": "m", "name": "M", "coinCost": 0}, headers=plain),
        client.patch("/admin/mascots/default", json={"name": "x"}, headers=plain),
        client.delete("/admin/mascots/default", headers=plain),
        client.post("/admin/images", files={"image": ("a.png", _PNG, "image/png")}, headers=plain),
    ]
    for call in calls:
        assert (await call).status_code == 403
    assert (await client.get("/admin/mascots")).status_code == 401


async def test_admin_image_upload(client, admin, image_storage):
    ok = await client.post("/admin/images", files={"image": ("a.png", _PNG, "image/png")}, headers=admin)
    assert ok.status_code == 200 and ok.json() == {"url": image_storage.url}
    webp = await client.post(
        "/admin/images", files={"image": ("a.webp", b"RIFF\x00\x00\x00\x00WEBP", "image/webp")}, headers=admin
    )
    assert webp.status_code == 200
    fake = await client.post("/admin/images", files={"image": ("a.png", b"not an image", "image/png")}, headers=admin)
    assert fake.status_code == 400
    heic = await client.post("/admin/images", files={"image": ("a.heic", b"x", "image/heic")}, headers=admin)
    assert heic.status_code == 400
    big = await client.post(
        "/admin/images", files={"image": ("a.png", _PNG + b"\x00" * (5 * 1024 * 1024), "image/png")}, headers=admin
    )
    assert big.status_code == 400
    assert len(image_storage.uploads) == 2


async def test_admin_image_upload_is_not_rate_limited(client, admin, image_storage):
    for _ in range(25):  # the owner endpoint stops at 20/min
        resp = await client.post("/admin/images", files={"image": ("a.png", _PNG, "image/png")}, headers=admin)
        assert resp.status_code == 200
