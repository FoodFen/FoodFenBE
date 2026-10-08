"""Owner endpoints: restaurant profile, dishes, image upload."""

from __future__ import annotations

import pytest


async def _admin(make_user):
    headers, _ = await make_user("admin@example.com", admin=True)
    return headers


async def _create(client, make_user, restaurant_body, email="owner@example.com"):
    headers, _ = await make_user(email)
    resp = await client.post("/restaurants", json=restaurant_body, headers=headers)
    assert resp.status_code == 201, resp.text
    return headers, resp.json()


async def test_create_returns_pending_restaurant_and_me_links_it(client, make_user, restaurant_body):
    headers, body = await _create(client, make_user, restaurant_body)
    assert body["status"] == "pending" and body["rejectionReason"] is None
    assert body["openingHours"] == "7:00-21:00" and body["latitude"] == 10.7769
    me = (await client.get("/auth/me", headers=headers)).json()
    assert me["restaurantId"] == body["id"]


async def test_second_restaurant_is_409(client, make_user, restaurant_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    assert (await client.post("/restaurants", json=restaurant_body, headers=headers)).status_code == 409


async def test_get_mine_without_restaurant_is_404(client, make_user):
    headers, _ = await make_user("nobody@example.com")
    assert (await client.get("/restaurants/mine", headers=headers)).status_code == 404


async def test_latitude_out_of_range_is_a_field_error(client, make_user, restaurant_body):
    headers, _ = await make_user("owner@example.com")
    resp = await client.post("/restaurants", json={**restaurant_body, "latitude": 91}, headers=headers)
    assert resp.status_code == 422
    assert "latitude" in resp.json()["errors"]


async def test_patch_null_required_field_is_422(client, make_user, restaurant_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    resp = await client.patch("/restaurants/mine", json={"name": None, "latitude": None}, headers=headers)
    assert resp.status_code == 422
    assert {"name", "latitude"} <= set(resp.json()["errors"])
    assert (await client.get("/restaurants/mine", headers=headers)).json()["name"] == "Quán Ngon"


@pytest.mark.skip(reason="needs Task 6")
async def test_editing_approved_restaurant_stays_live(client, make_user, restaurant_body):
    headers, body = await _create(client, make_user, restaurant_body)
    admin = await _admin(make_user)
    await client.post(f"/admin/restaurants/{body['id']}/review", json={"decision": "approved"}, headers=admin)
    resp = await client.patch("/restaurants/mine", json={"phone": "0911111111"}, headers=headers)
    assert resp.status_code == 200
    assert (resp.json()["phone"], resp.json()["status"]) == ("0911111111", "approved")


@pytest.mark.skip(reason="needs Task 6")
async def test_editing_rejected_restaurant_resubmits_it(client, make_user, restaurant_body):
    headers, body = await _create(client, make_user, restaurant_body)
    admin = await _admin(make_user)
    await client.post(
        f"/admin/restaurants/{body['id']}/review",
        json={"decision": "rejected", "reason": "need a real address"}, headers=admin,
    )
    mine = (await client.get("/restaurants/mine", headers=headers)).json()
    assert (mine["status"], mine["rejectionReason"]) == ("rejected", "need a real address")
    resp = await client.patch("/restaurants/mine", json={"address": "2 Lê Lợi"}, headers=headers)
    assert (resp.json()["status"], resp.json()["rejectionReason"]) == ("pending", None)


async def test_image_upload(client, make_user, image_storage):
    headers, _ = await make_user("owner@example.com")
    ok = await client.post(
        "/restaurants/mine/images", files={"image": ("a.webp", b"x" * 10, "image/webp")}, headers=headers
    )
    assert ok.status_code == 200 and ok.json() == {"url": image_storage.url}
    heic = await client.post(
        "/restaurants/mine/images", files={"image": ("a.heic", b"x", "image/heic")}, headers=headers
    )
    assert heic.status_code == 400 and "message" in heic.json()
    big = await client.post(
        "/restaurants/mine/images",
        files={"image": ("a.jpg", b"x" * (5 * 1024 * 1024 + 1), "image/jpeg")}, headers=headers,
    )
    assert big.status_code == 400
