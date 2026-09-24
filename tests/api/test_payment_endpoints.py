"""POST /payments/*, GET /subscriptions/me — end-to-end against the real app.

PayOS itself is faked (see `payment_provider` in conftest.py) — a test suite
should never depend on it.
"""

from __future__ import annotations

from decimal import Decimal

from src.application.ports.payment_provider import WebhookPayload
from src.infrastructure.di import CurrentPremiumUserDep
from src.main import app


async def test_checkout_returns_a_checkout_link(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["checkoutUrl"].startswith("https://pay.example/")
    assert body["status"] == "pending"
    assert Decimal(str(body["amount"])) == Decimal("49000")


async def test_checkout_requires_auth(client):
    resp = await client.post("/payments/checkout", json={"planType": "monthly"})
    assert resp.status_code == 401


async def test_webhook_with_valid_signature_marks_payment_paid(client, signed_up, payment_provider):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    checkout = (
        await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)
    ).json()

    payment_provider.next_webhook = WebhookPayload(order_code=checkout["orderCode"], succeeded=True)
    resp = await client.post("/payments/webhook", content=b"raw-webhook-body")
    assert resp.status_code == 200

    status_resp = await client.get(f"/payments/{checkout['orderCode']}", headers=headers)
    assert status_resp.json()["status"] == "paid"


async def test_webhook_with_invalid_signature_is_rejected(client, payment_provider):
    payment_provider.webhook_should_fail_signature = True
    resp = await client.post("/payments/webhook", content=b"raw-webhook-body")
    assert resp.status_code == 401


async def test_subscription_me_before_and_after_payment(client, signed_up, payment_provider):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    before = await client.get("/subscriptions/me", headers=headers)
    assert before.json()["hasActiveSubscription"] is False

    checkout = (
        await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)
    ).json()
    payment_provider.next_webhook = WebhookPayload(order_code=checkout["orderCode"], succeeded=True)
    await client.post("/payments/webhook", content=b"raw-webhook-body")

    after = await client.get("/subscriptions/me", headers=headers)
    assert after.json()["hasActiveSubscription"] is True
    assert after.json()["subscription"]["planType"] == "monthly"


async def test_cancel_rejects_an_already_paid_payment(client, signed_up, payment_provider):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    checkout = (
        await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)
    ).json()
    payment_provider.next_webhook = WebhookPayload(order_code=checkout["orderCode"], succeeded=True)
    await client.post("/payments/webhook", content=b"raw-webhook-body")

    resp = await client.post(f"/payments/{checkout['orderCode']}/cancel", json={}, headers=headers)
    assert resp.status_code == 400


@app.get("/__test/premium-only")
async def _premium_only(user: CurrentPremiumUserDep) -> dict[str, str]:
    return {"email": user.email}


async def test_premium_gate_blocks_free_user_then_passes_after_payment(
    client, signed_up, payment_provider
):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    blocked = await client.get("/__test/premium-only", headers=headers)
    assert blocked.status_code == 402

    checkout = (
        await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)
    ).json()
    payment_provider.next_webhook = WebhookPayload(order_code=checkout["orderCode"], succeeded=True)
    await client.post("/payments/webhook", content=b"raw-webhook-body")

    allowed = await client.get("/__test/premium-only", headers=headers)
    assert allowed.status_code == 200
