"""Owner endpoints: restaurant profile, dishes, image upload."""

from __future__ import annotations


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


async def test_editing_approved_restaurant_stays_live(client, make_user, restaurant_body):
    headers, body = await _create(client, make_user, restaurant_body)
    admin = await _admin(make_user)
    await client.post(f"/admin/restaurants/{body['id']}/review", json={"decision": "approved"}, headers=admin)
    resp = await client.patch("/restaurants/mine", json={"phone": "0911111111"}, headers=headers)
    assert resp.status_code == 200
    assert (resp.json()["phone"], resp.json()["status"]) == ("0911111111", "approved")


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
        "/restaurants/mine/images", files={"image": ("a.webp", b"RIFF\x00\x00\x00\x00WEBP", "image/webp")}, headers=headers
    )
    assert ok.status_code == 200 and ok.json() == {"url": image_storage.url}
    fake = await client.post(
        "/restaurants/mine/images", files={"image": ("a.png", b"not an image", "image/png")}, headers=headers
    )
    assert fake.status_code == 400 and len(image_storage.uploads) == 1
    heic = await client.post(
        "/restaurants/mine/images", files={"image": ("a.heic", b"x", "image/heic")}, headers=headers
    )
    assert heic.status_code == 400 and "message" in heic.json()
    big = await client.post(
        "/restaurants/mine/images",
        files={"image": ("a.jpg", b"\xff\xd8\xff" + b"x" * (5 * 1024 * 1024), "image/jpeg")}, headers=headers,
    )
    assert big.status_code == 400


async def test_dish_lifecycle(client, make_user, restaurant_body, dish_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    created = await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)
    assert created.status_code == 201
    dish = created.json()
    assert (dish["status"], dish["servingG"], dish["proteinG"], dish["price"]) == ("pending", 500, 30, 55000)
    assert dish["fiberG"] is None

    patched = await client.patch(
        f"/restaurants/mine/dishes/{dish['id']}", json={"kcal": 480, "fiberG": 3.5}, headers=headers
    )
    assert patched.status_code == 200
    assert (patched.json()["kcal"], patched.json()["fiberG"], patched.json()["status"]) == (480, 3.5, "pending")

    listed = (await client.get("/restaurants/mine/dishes", headers=headers)).json()
    assert [d["id"] for d in listed] == [dish["id"]]

    assert (await client.delete(f"/restaurants/mine/dishes/{dish['id']}", headers=headers)).status_code == 204
    assert (await client.get("/restaurants/mine/dishes", headers=headers)).json() == []


async def test_dish_without_restaurant_is_404(client, make_user, dish_body):
    headers, _ = await make_user("nobody@example.com")
    assert (await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)).status_code == 404


async def test_other_owners_dish_is_404(client, make_user, restaurant_body, dish_body):
    alice, _ = await _create(client, make_user, restaurant_body, "alice@example.com")
    bob, _ = await _create(client, make_user, restaurant_body, "bob@example.com")
    dish = (await client.post("/restaurants/mine/dishes", json=dish_body, headers=alice)).json()
    url = f"/restaurants/mine/dishes/{dish['id']}"
    assert (await client.patch(url, json={"kcal": 1}, headers=bob)).status_code == 404
    assert (await client.delete(url, headers=bob)).status_code == 404


async def test_patch_null_kcal_is_422(client, make_user, restaurant_body, dish_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    dish = (await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)).json()
    resp = await client.patch(f"/restaurants/mine/dishes/{dish['id']}", json={"kcal": None}, headers=headers)
    assert resp.status_code == 422 and "kcal" in resp.json()["errors"]
    cleared = await client.patch(
        f"/restaurants/mine/dishes/{dish['id']}", json={"fiberG": None}, headers=headers
    )
    assert cleared.status_code == 200 and cleared.json()["fiberG"] is None


async def test_negative_kcal_is_a_field_error(client, make_user, restaurant_body, dish_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    resp = await client.post("/restaurants/mine/dishes", json={**dish_body, "kcal": -1}, headers=headers)
    assert resp.status_code == 422 and "kcal" in resp.json()["errors"]


async def test_editing_approved_dish_returns_it_to_pending(client, make_user, restaurant_body, dish_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    dish = (await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)).json()
    admin = await _admin(make_user)
    await client.post(f"/admin/dishes/{dish['id']}/review", json={"decision": "approved"}, headers=admin)
    resp = await client.patch(f"/restaurants/mine/dishes/{dish['id']}", json={"price": 60000}, headers=headers)
    assert resp.json()["status"] == "pending"


async def test_empty_patch_does_not_resubmit_rejected_restaurant(client, make_user, restaurant_body):
    headers, body = await _create(client, make_user, restaurant_body)
    admin = await _admin(make_user)
    await client.post(
        f"/admin/restaurants/{body['id']}/review",
        json={"decision": "rejected", "reason": "need a real address"}, headers=admin,
    )
    resp = await client.patch("/restaurants/mine", json={}, headers=headers)
    assert resp.status_code == 200
    assert (resp.json()["status"], resp.json()["rejectionReason"]) == ("rejected", "need a real address")


async def test_empty_patch_keeps_approved_dish_approved(client, make_user, restaurant_body, dish_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    dish = (await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)).json()
    admin = await _admin(make_user)
    await client.post(f"/admin/dishes/{dish['id']}/review", json={"decision": "approved"}, headers=admin)
    resp = await client.patch(f"/restaurants/mine/dishes/{dish['id']}", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


async def test_unchanged_dish_patch_keeps_approved(client, make_user, restaurant_body, dish_body):
    headers, _ = await _create(client, make_user, restaurant_body)
    dish = (await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)).json()
    admin = await _admin(make_user)
    await client.post(f"/admin/dishes/{dish['id']}/review", json={"decision": "approved"}, headers=admin)
    resp = await client.patch(
        f"/restaurants/mine/dishes/{dish['id']}", json={"name": dish["name"]}, headers=headers
    )
    assert resp.status_code == 200 and resp.json()["status"] == "approved"


async def test_whitespace_only_name_is_a_field_error(client, make_user, restaurant_body):
    headers, _ = await make_user("owner@example.com")
    resp = await client.post("/restaurants", json={**restaurant_body, "name": "   "}, headers=headers)
    assert resp.status_code == 422 and "name" in resp.json()["errors"]
