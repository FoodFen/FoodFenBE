"""GET /admin/payments and GET /restaurants/mine/payments: filters, paging, row shape, access."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities.payment import Payment
from src.domain.enums import PaymentProvider, PaymentStatus, PlanType
from src.infrastructure.db.models.payment_model import PaymentORM
from src.infrastructure.db.session import engine

_NOW = datetime.now(UTC).replace(microsecond=0)


async def _pay(user_id, *, plan=PlanType.MONTHLY, status=PaymentStatus.PAID, provider=PaymentProvider.PAYOS,
               created=_NOW, amount=49000) -> int:
    """Insert a payment row with a chosen ``created_at``; returns its order code."""
    ad_days = 7 if plan is PlanType.AD_PACKAGE else None
    payment = Payment(
        id=uuid4(), user_id=user_id, plan_type=plan, amount=amount, status=status, provider=provider,
        created_at=created, paid_at=created if status is PaymentStatus.PAID else None, ad_days=ad_days,
    )
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add(PaymentORM.from_domain(payment))
        await session.commit()
        row = await session.get(PaymentORM, payment.id)
        return row.order_code


async def _admin_get(client, admin, query=""):
    resp = await client.get(f"/admin/payments?{query}", headers=admin)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _codes(body):
    return [p["orderCode"] for p in body["payments"]]


async def test_non_admin_is_forbidden(client, make_user):
    headers, _ = await make_user("plain@example.com")
    assert (await client.get("/admin/payments", headers=headers)).status_code == 403


async def test_admin_row_shape_and_restaurant_name_only_on_ad_rows(client, make_user, restaurant_body):
    admin, _ = await make_user("admin@example.com", admin=True)
    owner, owner_id = await make_user("owner@example.com")
    rid = (await client.post("/restaurants", json=restaurant_body, headers=owner)).json()["id"]
    ad = await _pay(owner_id, plan=PlanType.AD_PACKAGE, provider=PaymentProvider.MOMO, amount=99000)
    premium = await _pay(owner_id, created=_NOW - timedelta(minutes=1))

    body = await _admin_get(client, admin)
    assert body["total"] == 2 and body["nextCursor"] is None
    by_code = {p["orderCode"]: p for p in body["payments"]}
    assert set(by_code[ad]) == {
        "id", "orderCode", "userId", "userEmail", "userName", "restaurantId", "restaurantName", "planType",
        "provider", "amount", "status", "adDays", "createdAt", "paidAt",
    }
    row = by_code[ad]
    assert (row["userId"], row["userEmail"], row["userName"]) == (owner_id, "owner@example.com", "U")
    assert (row["restaurantId"], row["restaurantName"]) == (rid, restaurant_body["name"])
    assert (row["planType"], row["provider"], row["amount"], row["status"], row["adDays"]) == (
        "ad_package", "momo", 99000, "paid", 7,
    )
    assert isinstance(row["amount"], int) and row["paidAt"] is not None
    other = by_code[premium]
    assert (other["restaurantId"], other["restaurantName"], other["adDays"]) == (None, None, None)


async def test_admin_q_matches_email_substring_or_exact_order_code(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, alice = await make_user("Alice@example.com")
    _, bob = await make_user("bob@example.com")
    a = await _pay(alice)
    b = await _pay(bob)

    assert _codes(await _admin_get(client, admin, "q=ALICE")) == [a]
    assert _codes(await _admin_get(client, admin, f"q={b}")) == [b]
    assert (await _admin_get(client, admin, "q=nobody"))["total"] == 0
    assert (await _admin_get(client, admin, "q=%25"))["total"] == 0  # a literal percent sign, not a wildcard


async def test_admin_status_plan_type_and_provider_filters(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, uid = await make_user("u@example.com")
    paid = await _pay(uid)
    pending = await _pay(uid, status=PaymentStatus.PENDING)
    ad = await _pay(uid, plan=PlanType.AD_PACKAGE, provider=PaymentProvider.MOMO)

    assert _codes(await _admin_get(client, admin, "status=pending")) == [pending]
    assert _codes(await _admin_get(client, admin, "planType=ad_package")) == [ad]
    assert _codes(await _admin_get(client, admin, "provider=momo")) == [ad]
    assert sorted(_codes(await _admin_get(client, admin, "status=paid"))) == sorted([paid, ad])
    assert _codes(await _admin_get(client, admin, "status=paid&planType=monthly&provider=payos")) == [paid]


async def test_admin_date_range_uses_inclusive_vietnam_days(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, uid = await make_user("u@example.com")
    # 2026-03-10 00:30 Vietnam is 2026-03-09 17:30 UTC: a UTC-based filter would put it on the 9th.
    edge = await _pay(uid, created=datetime(2026, 3, 9, 17, 30, tzinfo=UTC))
    before = await _pay(uid, created=datetime(2026, 3, 9, 16, 59, tzinfo=UTC))  # still the 9th in Vietnam
    last = await _pay(uid, created=datetime(2026, 3, 10, 16, 59, tzinfo=UTC))  # 23:59 on the 10th
    after = await _pay(uid, created=datetime(2026, 3, 10, 17, 0, tzinfo=UTC))  # the 11th

    assert _codes(await _admin_get(client, admin, "from=2026-03-10&to=2026-03-10")) == [last, edge]
    assert _codes(await _admin_get(client, admin, "from=2026-03-11")) == [after]
    assert _codes(await _admin_get(client, admin, "to=2026-03-09")) == [before]


async def test_admin_paging_total_and_order(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, uid = await make_user("u@example.com")
    codes = [await _pay(uid, created=_NOW - timedelta(hours=i)) for i in range(5)]  # newest first

    first = await _admin_get(client, admin, "limit=2")
    assert (_codes(first), first["total"], first["nextCursor"]) == (codes[:2], 5, "2")
    second = await _admin_get(client, admin, f"limit=2&cursor={first['nextCursor']}")
    assert (_codes(second), second["nextCursor"]) == (codes[2:4], "4")
    last = await _admin_get(client, admin, f"limit=2&cursor={second['nextCursor']}")
    assert (_codes(last), last["total"], last["nextCursor"]) == (codes[4:], 5, None)


async def test_admin_total_counts_all_filter_matches_not_the_page(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, uid = await make_user("u@example.com")
    for i in range(3):
        await _pay(uid, created=_NOW - timedelta(hours=i))
    await _pay(uid, status=PaymentStatus.CANCELLED)

    body = await _admin_get(client, admin, "status=paid&limit=1")
    assert (len(body["payments"]), body["total"]) == (1, 3)


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=51", "cursor=abc", "cursor=-1", "status=bogus", "planType=bogus", "provider=bogus",
     "from=nope", f"q={'x' * 101}", "from=2026-03-11&to=2026-03-10"],
)
async def test_admin_bad_params_are_rejected(client, make_user, query):
    admin, _ = await make_user("admin@example.com", admin=True)
    assert (await client.get(f"/admin/payments?{query}", headers=admin)).status_code in (400, 422)


async def test_owner_sees_only_own_ad_payments_newest_first(client, make_user, restaurant_body):
    owner, owner_id = await make_user("owner@example.com")
    _, other_id = await make_user("other@example.com")
    await client.post("/restaurants", json=restaurant_body, headers=owner)
    old = await _pay(owner_id, plan=PlanType.AD_PACKAGE, created=_NOW - timedelta(days=1), amount=99000)
    new = await _pay(owner_id, plan=PlanType.AD_PACKAGE, status=PaymentStatus.PENDING, provider=PaymentProvider.MOMO)
    await _pay(owner_id)  # own, but Premium
    await _pay(other_id, plan=PlanType.AD_PACKAGE)  # another user's ad

    body = (await client.get("/restaurants/mine/payments", headers=owner)).json()
    assert _codes(body) == [new, old] and body["nextCursor"] is None
    newest, oldest = body["payments"]
    assert set(newest) == {"orderCode", "amount", "status", "provider", "adDays", "createdAt", "paidAt"}
    assert (newest["status"], newest["provider"], newest["paidAt"]) == ("pending", "momo", None)
    assert (oldest["amount"], oldest["adDays"]) == (99000, 7) and isinstance(oldest["amount"], int)


async def test_owner_paging(client, make_user, restaurant_body):
    owner, owner_id = await make_user("owner@example.com")
    await client.post("/restaurants", json=restaurant_body, headers=owner)
    codes = [await _pay(owner_id, plan=PlanType.AD_PACKAGE, created=_NOW - timedelta(hours=i)) for i in range(3)]

    first = (await client.get("/restaurants/mine/payments?limit=2", headers=owner)).json()
    assert (_codes(first), first["nextCursor"]) == (codes[:2], "2")
    last = (await client.get(f"/restaurants/mine/payments?limit=2&cursor={first['nextCursor']}", headers=owner)).json()
    assert (_codes(last), last["nextCursor"]) == (codes[2:], None)
    assert (await client.get("/restaurants/mine/payments?limit=0", headers=owner)).status_code == 422


async def test_owner_without_restaurant_is_404_and_auth_required(client, make_user):
    headers, _ = await make_user("norestaurant@example.com")
    assert (await client.get("/restaurants/mine/payments", headers=headers)).status_code == 404
    assert (await client.get("/restaurants/mine/payments")).status_code == 401
