"""Public diner endpoints: GET /dishes and GET /restaurants/{id}."""

from __future__ import annotations

_PRIVATE = {"status", "rejectionReason", "createdAt", "updatedAt", "reviewedAt", "userId", "restaurantId"}
_MISSING = "00000000-0000-0000-0000-000000000000"


async def _restaurant(client, make_user, restaurant_body, email, *, name="Quán Ngon", approve=None):
    """Owner + restaurant; ``approve`` is an admin's headers to approve it with."""
    headers, _ = await make_user(email)
    r = (await client.post("/restaurants", json={**restaurant_body, "name": name}, headers=headers)).json()
    if approve:
        await client.post(f"/admin/restaurants/{r['id']}/review", json={"decision": "approved"}, headers=approve)
    return headers, r["id"]


async def _dish(client, owner, dish_body, *, approve=None, reject=False, **fields):
    d = (await client.post("/restaurants/mine/dishes", json={**dish_body, **fields}, headers=owner)).json()
    if approve:
        body = {"decision": "rejected", "reason": "no"} if reject else {"decision": "approved"}
        await client.post(f"/admin/dishes/{d['id']}/review", json=body, headers=approve)
    return d["id"]


async def test_dishes_needs_a_token(client):
    assert (await client.get("/dishes")).status_code == 401


async def test_only_approved_dishes_of_approved_restaurants_are_public(
    client, make_user, restaurant_body, dish_body
):
    admin, _ = await make_user("admin@example.com", admin=True)
    owner, rid = await _restaurant(client, make_user, restaurant_body, "a@x.co", approve=admin)
    shown = await _dish(client, owner, dish_body, approve=admin, name="Shown")
    await _dish(client, owner, dish_body, name="Pending")
    await _dish(client, owner, dish_body, approve=admin, reject=True, name="Rejected")
    hidden_owner, _ = await _restaurant(client, make_user, restaurant_body, "b@x.co", name="Pending place")
    await _dish(client, hidden_owner, dish_body, name="Orphan")
    # Approve the dish through the admin API even though its restaurant is pending.
    orphan = (await client.get("/restaurants/mine/dishes", headers=hidden_owner)).json()[0]["id"]
    await client.post(f"/admin/dishes/{orphan}/review", json={"decision": "approved"}, headers=admin)

    reader, _ = await make_user("reader@example.com")
    body = (await client.get("/dishes", headers=reader)).json()
    assert [d["id"] for d in body["dishes"]] == [shown]
    dish = body["dishes"][0]
    assert dish["restaurant"] == {
        "id": rid, "name": "Quán Ngon", "address": "1 Lê Lợi, Q1",
        "latitude": 10.7769, "longitude": 106.7009,
    }
    assert not _PRIVATE & set(dish) and not _PRIVATE & set(dish["restaurant"])
    assert (dish["kcal"], dish["servingG"], dish["price"], dish["fits"]) == (450, 500, 55000, False)
    assert body["remainingKcal"] is None


async def test_remaining_kcal_reflects_goal_and_diary_on_the_date(
    client, make_user, restaurant_body, dish_body
):
    admin, _ = await make_user("admin@example.com", admin=True)
    owner, _ = await _restaurant(client, make_user, restaurant_body, "a@x.co", approve=admin)
    small = await _dish(client, owner, dish_body, approve=admin, name="Small", kcal=300)
    big = await _dish(client, owner, dish_body, approve=admin, name="Big", kcal=900)
    mid = await _dish(client, owner, dish_body, approve=admin, name="Mid", kcal=700)

    reader, _ = await make_user("reader@example.com")
    goal = {
        "targetKcal": 2000, "targetCarbsG": 200, "targetProteinG": 150, "targetFatG": 60,
        "targetWaterMl": 2500, "effectiveDate": "2026-10-01", "clientId": "g1",
    }
    assert (await client.post("/daily-goals", json=goal, headers=reader)).status_code == 200
    entry = {
        "name": "Lunch", "inputMethod": "manual", "totalKcal": 1200, "carbsG": 1, "proteinG": 1, "fatG": 1,
        "mealType": "lunch", "clientId": "e1", "loggedOn": "2026-10-09", "ingredients": [],
    }
    assert (await client.post("/food-entries", json=entry, headers=reader)).status_code == 200

    body = (await client.get("/dishes?date=2026-10-09", headers=reader)).json()
    assert body["remainingKcal"] == 800
    assert [(d["id"], d["fits"]) for d in body["dishes"]] == [(mid, True), (small, True), (big, False)]

    other_day = (await client.get("/dishes?date=2026-10-10", headers=reader)).json()
    assert other_day["remainingKcal"] == 2000
    assert all(d["fits"] for d in other_day["dishes"])

    before_goal = (await client.get("/dishes?date=2026-09-30", headers=reader)).json()
    assert before_goal["remainingKcal"] is None


async def test_public_restaurant_profile_lists_only_approved_dishes(
    client, make_user, restaurant_body, dish_body
):
    admin, _ = await make_user("admin@example.com", admin=True)
    owner, rid = await _restaurant(client, make_user, restaurant_body, "a@x.co", approve=admin)
    first = await _dish(client, owner, dish_body, approve=admin, name="First")
    await _dish(client, owner, dish_body, name="Pending")
    second = await _dish(client, owner, dish_body, approve=admin, name="Second")

    reader, _ = await make_user("reader@example.com")
    resp = await client.get(f"/restaurants/{rid}", headers=reader)
    assert resp.status_code == 200
    body = resp.json()
    assert {k: body[k] for k in ("id", "name", "address", "phone", "openingHours", "latitude", "longitude")} == {
        "id": rid, "name": "Quán Ngon", "address": "1 Lê Lợi, Q1", "phone": "0901234567",
        "openingHours": "7:00-21:00", "latitude": 10.7769, "longitude": 106.7009,
    }
    assert "description" in body and "imageUrl" in body
    assert not _PRIVATE & set(body)
    assert [d["id"] for d in body["dishes"]] == [first, second]
    assert not (_PRIVATE | {"fits", "restaurant"}) & set(body["dishes"][0])


async def test_pending_rejected_and_unknown_restaurants_are_404(client, make_user, restaurant_body):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, pending = await _restaurant(client, make_user, restaurant_body, "a@x.co")
    _, rejected = await _restaurant(client, make_user, restaurant_body, "b@x.co")
    await client.post(
        f"/admin/restaurants/{rejected}/review", json={"decision": "rejected", "reason": "no"}, headers=admin
    )
    reader, _ = await make_user("reader@example.com")
    for rid in (pending, rejected, _MISSING):
        assert (await client.get(f"/restaurants/{rid}", headers=reader)).status_code == 404
    assert (await client.get(f"/restaurants/{pending}")).status_code == 401


async def test_review_with_stale_expected_updated_at_is_409_and_current_is_200(
    client, make_user, restaurant_body, dish_body
):
    admin, _ = await make_user("admin@example.com", admin=True)
    owner, rid = await _restaurant(client, make_user, restaurant_body, "a@x.co")
    dish = (await client.post("/restaurants/mine/dishes", json=dish_body, headers=owner)).json()
    seen = (await client.get("/restaurants/mine", headers=owner)).json()["updatedAt"]
    # The owner edits after the admin loaded the page, so the admin's copy is stale.
    await client.patch("/restaurants/mine", json={"phone": "0911111111"}, headers=owner)
    await client.patch(f"/restaurants/mine/dishes/{dish['id']}", json={"kcal": 480}, headers=owner)

    for url, stale in ((f"/admin/restaurants/{rid}/review", seen), (f"/admin/dishes/{dish['id']}/review", dish["updatedAt"])):
        resp = await client.post(url, json={"decision": "approved", "expectedUpdatedAt": stale}, headers=admin)
        assert resp.status_code == 409 and "message" in resp.json()
    assert (await client.get("/restaurants/mine", headers=owner)).json()["status"] == "pending"

    current_r = (await client.get("/restaurants/mine", headers=owner)).json()["updatedAt"]
    current_d = (await client.get("/restaurants/mine/dishes", headers=owner)).json()[0]["updatedAt"]
    for url, current in ((f"/admin/restaurants/{rid}/review", current_r), (f"/admin/dishes/{dish['id']}/review", current_d)):
        resp = await client.post(url, json={"decision": "approved", "expectedUpdatedAt": current}, headers=admin)
        assert resp.status_code == 200 and resp.json()["status"] == "approved"
