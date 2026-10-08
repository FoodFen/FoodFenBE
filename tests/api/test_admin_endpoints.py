"""Admin guard, moderation and dashboard. End-to-end against the real app + SQLite."""

from __future__ import annotations

from src.domain.enums import UserRole


async def test_me_carries_role_and_null_restaurant(client, make_user):
    headers, _ = await make_user("plain@example.com")
    me = (await client.get("/auth/me", headers=headers)).json()
    assert me["role"] == "user"
    assert me["restaurantId"] is None


async def test_sign_in_session_carries_role(client, make_user):
    await make_user("boss@example.com", admin=True)
    resp = await client.post("/auth/sign-in", json={"email": "boss@example.com", "password": "s3cret-pass"})
    assert resp.json()["user"]["role"] == "admin"


async def test_non_admin_is_forbidden(client, make_user):
    headers, _ = await make_user("plain@example.com")
    resp = await client.get("/admin/restaurants", headers=headers)
    assert resp.status_code == 403
    assert "message" in resp.json()


async def test_admin_routes_need_a_token(client):
    assert (await client.get("/admin/restaurants")).status_code == 401


async def test_demoted_admin_is_forbidden_immediately(client, make_user, set_role):
    headers, user_id = await make_user("boss@example.com", admin=True)
    assert (await client.get("/admin/restaurants", headers=headers)).status_code == 200
    await set_role(user_id, UserRole.USER)
    assert (await client.get("/admin/restaurants", headers=headers)).status_code == 403


async def _restaurant_with(client, make_user, restaurant_body, dish_body, email, name, dishes=0):
    headers, _ = await make_user(email)
    r = (await client.post("/restaurants", json={**restaurant_body, "name": name}, headers=headers)).json()
    ids = []
    for _ in range(dishes):
        ids.append((await client.post("/restaurants/mine/dishes", json=dish_body, headers=headers)).json()["id"])
    return headers, r["id"], ids


async def _review(client, admin, kind, id_, decision, reason=None):
    body = {"decision": decision} | ({"reason": reason} if reason else {})
    return await client.post(f"/admin/{kind}/{id_}/review", json=body, headers=admin)


async def test_queue_includes_approved_restaurant_with_pending_dish(
    client, make_user, restaurant_body, dish_body
):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, a, _ = await _restaurant_with(client, make_user, restaurant_body, dish_body, "a@x.co", "A pending")
    _, b, b_dishes = await _restaurant_with(client, make_user, restaurant_body, dish_body, "b@x.co", "B done", 1)
    _, c, c_dishes = await _restaurant_with(client, make_user, restaurant_body, dish_body, "c@x.co", "C new dish", 2)
    _, d, _ = await _restaurant_with(client, make_user, restaurant_body, dish_body, "d@x.co", "D rejected", 1)
    for rid in (b, c):
        await _review(client, admin, "restaurants", rid, "approved")
    await _review(client, admin, "dishes", b_dishes[0], "approved")
    await _review(client, admin, "dishes", c_dishes[0], "approved")
    await _review(client, admin, "restaurants", d, "rejected", "fake")

    queue = (await client.get("/admin/restaurants?needsReview=true", headers=admin)).json()
    by_name = {row["name"]: row for row in queue}
    assert set(by_name) == {"A pending", "C new dish"}
    assert (by_name["C new dish"]["dishCount"], by_name["C new dish"]["pendingDishCount"]) == (2, 1)
    assert by_name["A pending"]["ownerEmail"] == "a@x.co"

    everything = (await client.get("/admin/restaurants", headers=admin)).json()
    assert len(everything) == 4
    rejected = (await client.get("/admin/restaurants?status=rejected", headers=admin)).json()
    assert [(r["name"], r["rejectionReason"]) for r in rejected] == [("D rejected", "fake")]


async def test_detail_includes_full_menu(client, make_user, restaurant_body, dish_body):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, rid, dish_ids = await _restaurant_with(client, make_user, restaurant_body, dish_body, "o@x.co", "R", 2)
    detail = (await client.get(f"/admin/restaurants/{rid}", headers=admin)).json()
    assert detail["restaurant"]["id"] == rid
    assert [d["id"] for d in detail["dishes"]] == dish_ids
    assert detail["dishes"][0]["kcal"] == 450


async def test_unknown_restaurant_is_404(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    missing = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"/admin/restaurants/{missing}", headers=admin)).status_code == 404
    assert (await _review(client, admin, "dishes", missing, "approved")).status_code == 404


async def test_reject_requires_reason_field_error(client, make_user, restaurant_body, dish_body):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, rid, _ = await _restaurant_with(client, make_user, restaurant_body, dish_body, "o@x.co", "R")
    resp = await _review(client, admin, "restaurants", rid, "rejected")
    assert resp.status_code == 422 and "reason" in resp.json()["errors"]


async def test_repeat_review_is_idempotent_and_takedown_works(client, make_user, restaurant_body, dish_body):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, rid, _ = await _restaurant_with(client, make_user, restaurant_body, dish_body, "o@x.co", "R")
    first = await _review(client, admin, "restaurants", rid, "approved")
    again = await _review(client, admin, "restaurants", rid, "approved")
    assert first.status_code == again.status_code == 200
    assert again.json()["status"] == "approved"
    down = await _review(client, admin, "restaurants", rid, "rejected", "food safety report")
    assert (down.json()["status"], down.json()["rejectionReason"]) == ("rejected", "food safety report")


async def test_dashboard_sums_only_paid_payments(client, make_user, restaurant_body):
    from datetime import UTC, datetime, timedelta, timezone
    from decimal import Decimal
    from uuid import uuid4

    from src.domain.enums import PaymentStatus, PlanType
    from src.infrastructure.db.models.payment_model import PaymentORM
    from src.infrastructure.db.session import SessionLocal

    admin, admin_id = await make_user("admin@example.com", admin=True)
    owner, _ = await make_user("owner@example.com")
    await client.post("/restaurants", json=restaurant_body, headers=owner)
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        session.add_all([
            PaymentORM(id=uuid4(), user_id=admin_id, plan_type=PlanType.MONTHLY, amount=Decimal("99000"),
                       status=PaymentStatus.PAID, created_at=now, paid_at=now),
            PaymentORM(id=uuid4(), user_id=admin_id, plan_type=PlanType.ANNUAL, amount=Decimal("990000"),
                       status=PaymentStatus.PENDING, created_at=now, paid_at=None),
        ])
        await session.commit()

    today = datetime.now(timezone(timedelta(hours=7))).date().isoformat()
    resp = await client.get(f"/admin/dashboard?from={today}&to={today}", headers=admin)
    assert resp.status_code == 200
    body = resp.json()
    assert body["totals"] == {"premiumRevenue": 99000, "adRevenue": 0, "newUsers": 2, "newRestaurants": 1}
    assert body["daily"] == [{
        "date": today, "premiumRevenue": 99000, "adRevenue": 0, "newUsers": 2, "newRestaurants": 1,
    }]
    assert (body["from"], body["to"]) == (today, today)


async def test_dashboard_bad_range_is_400(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    resp = await client.get("/admin/dashboard?from=2026-10-09&to=2026-10-08", headers=admin)
    assert resp.status_code == 400
