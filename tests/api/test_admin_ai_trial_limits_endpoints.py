"""Admin-editable AI free-trial limits: GET/PUT /admin/ai/trial-limits, and /ai/food/quota honouring them."""

import pytest
import pytest_asyncio

_URL = "/admin/ai/trial-limits"


@pytest_asyncio.fixture
async def admin(make_user):
    headers, _ = await make_user("admin@example.com", admin=True)
    return headers


async def test_get_defaults(client, admin):
    resp = await client.get(_URL, headers=admin)

    assert (resp.status_code, resp.json()) == (200, {"guestLimit": 3, "signedInLimit": 5})


async def test_put_then_get(client, admin):
    resp = await client.put(_URL, json={"guestLimit": 0, "signedInLimit": 100}, headers=admin)

    assert (resp.status_code, resp.json()) == (200, {"guestLimit": 0, "signedInLimit": 100})
    assert (await client.get(_URL, headers=admin)).json() == {"guestLimit": 0, "signedInLimit": 100}


async def test_put_again_updates_the_single_row(client, admin):
    await client.put(_URL, json={"guestLimit": 1, "signedInLimit": 2}, headers=admin)
    await client.put(_URL, json={"guestLimit": 4, "signedInLimit": 6}, headers=admin)

    assert (await client.get(_URL, headers=admin)).json() == {"guestLimit": 4, "signedInLimit": 6}


async def test_put_out_of_range_is_a_coded_422(client, admin):
    resp = await client.put(_URL, json={"guestLimit": 3, "signedInLimit": 101}, headers=admin)

    assert resp.status_code == 422
    assert resp.json()["code"] == "limit_out_of_range"
    assert resp.json()["field"] == "signedInLimit"
    assert (await client.get(_URL, headers=admin)).json() == {"guestLimit": 3, "signedInLimit": 5}


async def test_put_requires_both_fields(client, admin):
    assert (await client.put(_URL, json={"guestLimit": 3}, headers=admin)).status_code == 422


@pytest.mark.parametrize("method", ["get", "put"])
async def test_non_admin_403_anonymous_401(client, make_user, method):
    user, _ = await make_user("user@example.com")
    kwargs = {"json": {"guestLimit": 1, "signedInLimit": 1}} if method == "put" else {}

    assert (await getattr(client, method)(_URL, headers=user, **kwargs)).status_code == 403
    assert (await getattr(client, method)(_URL, **kwargs)).status_code == 401


async def test_quota_shows_the_new_guest_limit(client, admin):
    await client.put(_URL, json={"guestLimit": 1, "signedInLimit": 5}, headers=admin)

    body = (await client.get("/ai/food/quota", headers={"X-Device-Id": "device-aaaaaaaa"})).json()

    assert body["image"] == {"limit": 1, "remaining": 1}
