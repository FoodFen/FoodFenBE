"""POST /payments/*, GET /subscriptions/me — end-to-end against the real app.

PayOS itself is faked (see `payment_provider` in conftest.py) — a test suite
should never depend on it.
"""

from __future__ import annotations

from decimal import Decimal

from src.application.ports.payment_provider import ProviderPaymentStatus, WebhookPayload
from src.domain.enums import PaymentProvider, PaymentStatus
from src.infrastructure.di import CurrentPremiumUserDep
from src.main import app


async def test_checkout_returns_a_checkout_link(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["checkoutUrl"].startswith("https://pay.example/")
    assert body["status"] == "pending"
    assert isinstance(body["amount"], (int, float))
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
    assert isinstance(after.json()["subscription"]["price"], (int, float))
    assert Decimal(str(after.json()["subscription"]["price"])) == Decimal("49000")


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


async def test_checkout_without_provider_defaults_to_payos(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    body = (
        await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)
    ).json()

    assert body["provider"] == "payos"
    assert body["qrCode"] == f"qr-{body['orderCode']}"
    assert body["deeplink"] is None


async def test_checkout_with_momo_returns_a_deeplink_and_no_qr(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/payments/checkout", json={"planType": "monthly", "provider": "momo"}, headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "momo"
    assert body["deeplink"] == f"momo://pay/{body['orderCode']}"
    assert body["qrCode"] is None
    assert body["checkoutUrl"].startswith("https://pay.example/")


async def test_checkout_with_an_unknown_provider_is_rejected(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post(
        "/payments/checkout", json={"planType": "monthly", "provider": "zalopay"}, headers=headers
    )

    assert resp.status_code == 422


async def test_checkout_with_a_disabled_provider_is_rejected(client, signed_up, payment_providers):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    del payment_providers[PaymentProvider.MOMO]

    resp = await client.post(
        "/payments/checkout", json={"planType": "monthly", "provider": "momo"}, headers=headers
    )

    assert resp.status_code == 422


async def test_momo_webhook_marks_a_momo_payment_paid(client, signed_up, payment_providers):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    checkout = (
        await client.post(
            "/payments/checkout", json={"planType": "monthly", "provider": "momo"}, headers=headers
        )
    ).json()

    payment_providers[PaymentProvider.MOMO].next_webhook = WebhookPayload(
        order_code=checkout["orderCode"], succeeded=True
    )
    resp = await client.post("/payments/webhook/momo", content=b"raw-ipn-body")

    assert resp.status_code == 204
    status_resp = await client.get(f"/payments/{checkout['orderCode']}", headers=headers)
    assert status_resp.json()["status"] == "paid"


async def test_momo_webhook_with_invalid_signature_is_rejected(client, payment_providers):
    payment_providers[PaymentProvider.MOMO].webhook_should_fail_signature = True

    resp = await client.post("/payments/webhook/momo", content=b"raw-ipn-body")

    assert resp.status_code == 401


async def test_status_of_a_momo_payment_reconciles_with_momo(client, signed_up, payment_providers):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    checkout = (
        await client.post(
            "/payments/checkout", json={"planType": "monthly", "provider": "momo"}, headers=headers
        )
    ).json()
    order_code = checkout["orderCode"]
    payment_providers[PaymentProvider.MOMO].status_by_order_code[order_code] = ProviderPaymentStatus(
        order_code=order_code, status=PaymentStatus.PAID, succeeded=True
    )

    resp = await client.get(f"/payments/{order_code}", headers=headers)

    assert resp.json()["status"] == "paid"


async def test_cancelling_a_momo_payment_goes_to_momo(client, signed_up, payment_providers):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    checkout = (
        await client.post(
            "/payments/checkout", json={"planType": "monthly", "provider": "momo"}, headers=headers
        )
    ).json()
    order_code = checkout["orderCode"]

    resp = await client.post(f"/payments/{order_code}/cancel", json={}, headers=headers)

    assert resp.json()["status"] == "cancelled"
    assert order_code in payment_providers[PaymentProvider.MOMO].cancelled
    assert order_code not in payment_providers[PaymentProvider.PAYOS].cancelled
