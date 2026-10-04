"""GET /payments/plans — the prices the paywall shows come from the same settings as checkout."""

from __future__ import annotations

import pytest_asyncio

from src.infrastructure.config import settings


@pytest_asyncio.fixture
async def auth(signed_up):
    return {"Authorization": f"Bearer {signed_up['accessToken']}"}


async def test_plans_require_auth(client):
    assert (await client.get("/payments/plans")).status_code == 401


async def test_plans_list_the_configured_prices(client, auth):
    resp = await client.get("/payments/plans", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == {
        "plans": [
            {"planType": "monthly", "priceVnd": settings.payos_monthly_price_vnd},
            {"planType": "annual", "priceVnd": settings.payos_annual_price_vnd},
        ]
    }
