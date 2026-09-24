"""POST/GET /food-entries — end-to-end against the real app.

Proves the fiber_g Premium gate end-to-end: a free user's submitted fiber_g
is dropped, a Premium user's (paid via the fake PayOS provider) is kept.
"""

from __future__ import annotations

from src.application.ports.payment_provider import WebhookPayload

_BODY = {
    "name": "Grilled chicken with rice",
    "inputMethod": "manual",
    "totalKcal": 650,
    "carbsG": 70.0,
    "proteinG": 45.0,
    "fatG": 15.0,
    "fiberG": 8.0,
    "ingredients": [
        {
            "name": "chicken breast",
            "quantityG": 200.0,
            "kcal": 330,
            "carbsG": 0.0,
            "proteinG": 40.0,
            "fatG": 15.0,
            "fiberG": 2.0,
        }
    ],
}


async def _make_premium(client, headers, payment_provider) -> None:
    checkout = (
        await client.post("/payments/checkout", json={"planType": "monthly"}, headers=headers)
    ).json()
    payment_provider.next_webhook = WebhookPayload(order_code=checkout["orderCode"], succeeded=True)
    await client.post("/payments/webhook", content=b"raw-webhook-body")


async def test_free_user_gets_fiber_g_dropped(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/food-entries", json=_BODY, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["fiberG"] is None
    assert body["ingredients"][0]["fiberG"] is None
    assert body["totalKcal"] == 650  # everything else is untouched


async def test_premium_user_keeps_fiber_g(client, signed_up, payment_provider):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    await _make_premium(client, headers, payment_provider)

    resp = await client.post("/food-entries", json=_BODY, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["fiberG"] == 8.0
    assert body["ingredients"][0]["fiberG"] == 2.0


async def test_create_requires_auth(client):
    resp = await client.post("/food-entries", json=_BODY)
    assert resp.status_code == 401


async def test_get_returns_the_owners_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    resp = await client.get(f"/food-entries/{created['id']}", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["name"] == "Grilled chicken with rice"


async def test_get_rejects_another_users_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    other = await client.post(
        "/auth/sign-up",
        json={"email": "other@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.get(f"/food-entries/{created['id']}", headers=other_headers)
    assert resp.status_code == 404
