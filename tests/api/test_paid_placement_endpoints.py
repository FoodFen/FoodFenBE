"""Paid placement: owner ad checkout, the sponsored section of GET /dishes, admin packages, dashboard split."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from src.application.ports.payment_provider import WebhookPayload
from src.domain.enums import PaymentStatus

_VN = timezone(timedelta(hours=7))
_MISSING = "00000000-0000-0000-0000-000000000000"
_GOAL = {
    "targetKcal": 2000, "targetCarbsG": 200, "targetProteinG": 150, "targetFatG": 60,
    "targetWaterMl": 2500, "effectiveDate": "2026-10-01", "clientId": "g1",
}


async def _package(client, admin, days=7, price=99000, **extra):
    resp = await client.post("/admin/ad-packages", json={"days": days, "priceVnd": price, **extra}, headers=admin)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _place(client, make_user, admin, restaurant_body, dish_body, email, *, kcal=450, approve=True):
    """An owner with one dish; both approved unless ``approve`` is False."""
    owner, _ = await make_user(email)
    r = (await client.post("/restaurants", json={**restaurant_body, "name": email}, headers=owner)).json()
    d = (await client.post("/restaurants/mine/dishes", json={**dish_body, "kcal": kcal}, headers=owner)).json()
    if approve:
        await client.post(f"/admin/restaurants/{r['id']}/review", json={"decision": "approved"}, headers=admin)
        await client.post(f"/admin/dishes/{d['id']}/review", json={"decision": "approved"}, headers=admin)
    return owner, r["id"], d["id"]


async def _pay(client, payment_provider, order_code):
    payment_provider.next_webhook = WebhookPayload(order_code=order_code, status=PaymentStatus.PAID, succeeded=True)
    assert (await client.post("/payments/webhook", content=b"x")).status_code == 200


async def _buy(client, payment_provider, owner, package_id):
    resp = await client.post(
        "/restaurants/mine/ads/checkout", json={"packageId": package_id, "provider": "payos"}, headers=owner
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    await _pay(client, payment_provider, body["orderCode"])
    return body


async def _diner(client, make_user, email="diner@example.com", goal=True):
    headers, _ = await make_user(email)
    if goal:
        assert (await client.post("/daily-goals", json=_GOAL, headers=headers)).status_code == 200
    return headers


async def _featured_until(client, owner):
    value = (await client.get("/restaurants/mine/ads", headers=owner)).json()["featuredUntil"]
    return datetime.fromisoformat(value)


async def test_paid_restaurant_is_featured_on_page_one_only_and_impressions_are_counted(
    client, make_user, restaurant_body, dish_body, payment_provider
):
    admin, _ = await make_user("admin@example.com", admin=True)
    package = await _package(client, admin)
    owner, rid, dish = await _place(client, make_user, admin, restaurant_body, dish_body, "a@x.co")
    await _place(client, make_user, admin, restaurant_body, dish_body, "free@x.co")  # not paying
    diner = await _diner(client, make_user)

    assert (await client.get("/dishes", headers=diner)).json()["featured"] == []

    checkout = await _buy(client, payment_provider, owner, package["id"])
    assert (checkout["planType"], checkout["amount"]) == ("ad_package", 99000)

    page = (await client.get("/dishes?limit=1", headers=diner)).json()
    assert [d["id"] for d in page["featured"]] == [dish]
    assert page["featured"][0]["fits"] is True and page["featured"][0]["restaurant"]["id"] == rid
    assert len(page["dishes"]) == 1  # the main list is untouched: ranked by health, no sponsor label

    page2 = (await client.get(f"/dishes?limit=1&cursor={page['nextCursor']}", headers=diner)).json()
    assert page2["featured"] == []

    ads = (await client.get("/restaurants/mine/ads", headers=owner)).json()
    today = datetime.now(_VN).date().isoformat()
    assert len(ads["impressions"]) == 30 and ads["impressions"][-1] == {"date": today, "count": 1}
    assert sum(i["count"] for i in ads["impressions"]) == 1  # page 2 did not count
    remaining = datetime.fromisoformat(ads["featuredUntil"]) - datetime.now(UTC)
    assert timedelta(days=6, hours=23) < remaining <= timedelta(days=7)


async def test_buying_again_while_featured_extends_from_the_current_end(
    client, make_user, restaurant_body, dish_body, payment_provider
):
    admin, _ = await make_user("admin@example.com", admin=True)
    package = await _package(client, admin)
    owner, _, _ = await _place(client, make_user, admin, restaurant_body, dish_body, "a@x.co")
    await _buy(client, payment_provider, owner, package["id"])
    first = await _featured_until(client, owner)
    await _buy(client, payment_provider, owner, package["id"])
    assert await _featured_until(client, owner) - first == timedelta(days=7)


async def test_a_sponsored_dish_that_does_not_fit_is_not_featured(
    client, make_user, restaurant_body, dish_body, payment_provider
):
    admin, _ = await make_user("admin@example.com", admin=True)
    package = await _package(client, admin)
    owner, _, _ = await _place(client, make_user, admin, restaurant_body, dish_body, "a@x.co", kcal=3000)
    for email, kcal in (("b@x.co", 100), ("c@x.co", 200), ("d@x.co", 300)):  # enough fitting dishes: no top-up
        await _place(client, make_user, admin, restaurant_body, dish_body, email, kcal=kcal)
    await _buy(client, payment_provider, owner, package["id"])
    diner = await _diner(client, make_user)

    assert (await client.get("/dishes", headers=diner)).json()["featured"] == []
    ads = (await client.get("/restaurants/mine/ads", headers=owner)).json()
    assert sum(i["count"] for i in ads["impressions"]) == 0  # no exposure, no impression


async def test_no_goal_means_no_sponsored_section(
    client, make_user, restaurant_body, dish_body, payment_provider
):
    admin, _ = await make_user("admin@example.com", admin=True)
    package = await _package(client, admin)
    owner, _, _ = await _place(client, make_user, admin, restaurant_body, dish_body, "a@x.co")
    await _buy(client, payment_provider, owner, package["id"])
    diner = await _diner(client, make_user, goal=False)
    assert (await client.get("/dishes", headers=diner)).json()["featured"] == []


async def test_search_only_features_matching_dishes(
    client, make_user, restaurant_body, dish_body, payment_provider
):
    admin, _ = await make_user("admin@example.com", admin=True)
    package = await _package(client, admin)
    owner, _, _ = await _place(client, make_user, admin, restaurant_body, dish_body, "a@x.co")  # "Phở bò"
    await _buy(client, payment_provider, owner, package["id"])
    diner = await _diner(client, make_user)
    assert (await client.get("/dishes?q=bun", headers=diner)).json()["featured"] == []
    assert len((await client.get("/dishes?q=pho", headers=diner)).json()["featured"]) == 1


async def test_checkout_needs_an_approved_restaurant(client, make_user, restaurant_body, dish_body):
    admin, _ = await make_user("admin@example.com", admin=True)
    package = await _package(client, admin)
    owner, _, _ = await _place(client, make_user, admin, restaurant_body, dish_body, "a@x.co", approve=False)
    resp = await client.post(
        "/restaurants/mine/ads/checkout", json={"packageId": package["id"], "provider": "payos"}, headers=owner
    )
    assert resp.status_code == 409 and resp.json()["error"] == "restaurant_not_approved"


async def test_checkout_unknown_or_inactive_package_is_404(client, make_user, restaurant_body, dish_body):
    admin, _ = await make_user("admin@example.com", admin=True)
    off = await _package(client, admin, active=False)
    owner, _, _ = await _place(client, make_user, admin, restaurant_body, dish_body, "a@x.co")
    for package_id in (off["id"], _MISSING):
        resp = await client.post(
            "/restaurants/mine/ads/checkout", json={"packageId": package_id, "provider": "payos"}, headers=owner
        )
        assert resp.status_code == 404


async def test_ads_routes_need_a_restaurant(client, make_user):
    headers, _ = await make_user("nobody@example.com")
    assert (await client.get("/restaurants/mine/ads", headers=headers)).status_code == 404
    resp = await client.post(
        "/restaurants/mine/ads/checkout", json={"packageId": _MISSING, "provider": "payos"}, headers=headers
    )
    assert resp.status_code == 404


async def test_ad_routes_need_a_token(client):
    assert (await client.get("/restaurants/mine/ads")).status_code == 401
    resp = await client.post("/restaurants/mine/ads/checkout", json={"packageId": _MISSING, "provider": "payos"})
    assert resp.status_code == 401


async def test_owner_sees_only_active_packages_by_days_with_integer_prices(
    client, make_user, restaurant_body, dish_body
):
    admin, _ = await make_user("admin@example.com", admin=True)
    await _package(client, admin, days=30, price=299000)
    await _package(client, admin, days=7, price=99000)
    await _package(client, admin, days=1, price=19000, active=False)
    owner, _, _ = await _place(client, make_user, admin, restaurant_body, dish_body, "a@x.co")
    ads = (await client.get("/restaurants/mine/ads", headers=owner)).json()
    assert ads["featuredUntil"] is None
    assert [(p["days"], p["priceVnd"]) for p in ads["packages"]] == [(7, 99000), (30, 299000)]
    assert all(type(p["days"]) is int and type(p["priceVnd"]) is int for p in ads["packages"])  # JSON numbers
    assert set(ads["packages"][0]) == {"id", "days", "priceVnd"}


async def test_admin_package_crud_wire_shape(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    created = await _package(client, admin)
    assert set(created) == {"id", "days", "priceVnd", "active", "createdAt"}
    assert type(created["priceVnd"]) is int and type(created["days"]) is int  # JSON numbers, not strings
    assert created["active"] is True

    patched = await client.patch(
        f"/admin/ad-packages/{created['id']}", json={"priceVnd": 120000, "active": False}, headers=admin
    )
    assert patched.status_code == 200
    body = patched.json()
    assert (body["days"], body["priceVnd"], body["active"]) == (7, 120000, False)
    assert type(body["priceVnd"]) is int

    listed = (await client.get("/admin/ad-packages", headers=admin)).json()  # inactive ones included
    assert [(p["id"], p["active"]) for p in listed] == [(created["id"], False)]
    assert type(listed[0]["priceVnd"]) is int


async def test_admin_package_validation_and_unknown_id(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    for bad in ({"days": 0, "priceVnd": 1}, {"days": 7, "priceVnd": 0}, {"days": 7}):
        assert (await client.post("/admin/ad-packages", json=bad, headers=admin)).status_code == 422
    assert (await client.patch(f"/admin/ad-packages/{_MISSING}", json={"days": 3}, headers=admin)).status_code == 404
    created = await _package(client, admin)
    resp = await client.patch(f"/admin/ad-packages/{created['id']}", json={"days": 0}, headers=admin)
    assert resp.status_code == 422


async def test_admin_package_routes_are_admin_only(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    created = await _package(client, admin)
    plain, _ = await make_user("plain@example.com")
    assert (await client.get("/admin/ad-packages", headers=plain)).status_code == 403
    assert (await client.post("/admin/ad-packages", json={"days": 1, "priceVnd": 1}, headers=plain)).status_code == 403
    patch = await client.patch(f"/admin/ad-packages/{created['id']}", json={"days": 2}, headers=plain)
    assert patch.status_code == 403


async def test_dashboard_splits_ad_and_premium_revenue(
    client, make_user, restaurant_body, dish_body, payment_provider
):
    admin, _ = await make_user("admin@example.com", admin=True)
    package = await _package(client, admin, price=99000)
    owner, _, _ = await _place(client, make_user, admin, restaurant_body, dish_body, "a@x.co")
    await _buy(client, payment_provider, owner, package["id"])
    buyer, _ = await make_user("buyer@example.com")
    checkout = (await client.post("/payments/checkout", json={"planType": "monthly"}, headers=buyer)).json()
    await _pay(client, payment_provider, checkout["orderCode"])

    today = datetime.now(_VN).date().isoformat()
    totals = (await client.get(f"/admin/dashboard?from={today}&to={today}", headers=admin)).json()["totals"]
    assert (totals["adRevenue"], totals["premiumRevenue"]) == (99000, 49000)


async def test_generic_checkout_rejects_ad_package(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.post("/payments/checkout", json={"planType": "ad_package"}, headers=headers)
    assert resp.status_code == 422
