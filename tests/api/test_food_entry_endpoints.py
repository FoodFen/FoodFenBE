"""POST/GET /food-entries — end-to-end against the real app.

fiber_g is always stored regardless of tier — Premium only gates its
*display* client-side (mirrors ai-food-capture.md's "no Premium check").
"""

from __future__ import annotations

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


async def test_fiber_g_is_stored_for_a_free_user(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    resp = await client.post("/food-entries", json=_BODY, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["fiberG"] == 8.0
    assert body["ingredients"][0]["fiberG"] == 2.0
    assert body["totalKcal"] == 650


async def test_create_requires_auth(client):
    resp = await client.post("/food-entries", json=_BODY)
    assert resp.status_code == 401


async def test_get_returns_the_owners_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    resp = await client.get(f"/food-entries/{created['id']}", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["name"] == "Grilled chicken with rice"
    assert resp.json()["fiberG"] == 8.0


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
