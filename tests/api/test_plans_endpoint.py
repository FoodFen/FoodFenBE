"""GET /payments/plans — public: a guest looking at the paywall needs the prices without signing in.
They are the same settings checkout charges."""

from __future__ import annotations

from src.infrastructure.config import settings


async def test_plans_are_public_and_list_the_configured_prices(client):
    resp = await client.get("/payments/plans")  # no Authorization header
    assert resp.status_code == 200
    assert resp.json() == {
        "plans": [
            {"planType": "monthly", "priceVnd": settings.payos_monthly_price_vnd},
            {"planType": "annual", "priceVnd": settings.payos_annual_price_vnd},
        ]
    }


async def test_checkout_still_requires_auth(client):
    resp = await client.post("/payments/checkout", json={"planType": "monthly"})
    assert resp.status_code == 401
