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
    "mealType": "lunch",
    "clientId": "entry_1",
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


async def test_submitted_logged_on_round_trips_through_create_and_list(client, signed_up):
    """logged_on must be exactly what the client sends, never re-derived from
    the server's UTC clock — otherwise a user near UTC midnight silently gets
    the wrong day stored (see docs/superpowers/plans/2026-09-25-diary-sync-pull.md
    final review, Important #2)."""
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    body = {**_BODY, "loggedOn": "2020-06-15"}

    created = (await client.post("/food-entries", json=body, headers=headers)).json()
    assert created["loggedOn"] == "2020-06-15"

    resp = await client.get(
        "/food-entries", params={"from": "2020-06-15", "to": "2020-06-15"}, headers=headers
    )
    assert resp.status_code == 200
    assert [e["id"] for e in resp.json()] == [created["id"]]


async def test_list_returns_entries_in_the_requested_range(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    today = created["loggedOn"]

    resp = await client.get(
        "/food-entries", params={"from": today, "to": today}, headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == created["id"]
    assert body[0]["mealType"] == "lunch"
    assert body[0]["userId"] == signed_up["user"]["id"]
    assert body[0]["ingredients"][0]["foodEntryId"] == created["id"]


async def test_posting_the_same_client_id_twice_returns_the_same_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}

    first = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    second = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    assert first["id"] == second["id"]


async def test_post_stores_the_submitted_logged_at_not_the_servers_clock(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    body = {**_BODY, "clientId": "entry_2", "loggedAt": "2026-01-15T08:00:00Z"}

    resp = await client.post("/food-entries", json=body, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["loggedAt"].startswith("2026-01-15T08:00:00")


async def test_patch_stores_the_submitted_logged_at(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    resp = await client.patch(
        f"/food-entries/{created['id']}",
        json={**_BODY, "loggedAt": "2026-01-15T08:00:00Z"},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["loggedAt"].startswith("2026-01-15T08:00:00")


async def test_create_requires_client_id(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    body = {k: v for k, v in _BODY.items() if k != "clientId"}

    resp = await client.post("/food-entries", json=body, headers=headers)

    assert resp.status_code == 422


async def test_patch_replaces_the_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    patch_body = {**_BODY, "name": "Changed", "mealType": "dinner"}
    resp = await client.patch(f"/food-entries/{created['id']}", json=patch_body, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["name"] == "Changed"
    assert resp.json()["mealType"] == "dinner"


async def test_patch_rejects_another_users_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    other = await client.post(
        "/auth/sign-up",
        json={"email": "patcher@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.patch(
        f"/food-entries/{created['id']}", json=_BODY, headers=other_headers
    )
    assert resp.status_code == 404


async def test_delete_soft_deletes_and_it_disappears_from_get_and_list(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    resp = await client.delete(f"/food-entries/{created['id']}", headers=headers)
    assert resp.status_code == 204

    assert (await client.get(f"/food-entries/{created['id']}", headers=headers)).status_code == 404

    list_resp = await client.get(
        "/food-entries",
        params={"from": created["loggedOn"], "to": created["loggedOn"]},
        headers=headers,
    )
    assert list_resp.json() == []


async def test_delete_twice_returns_404_the_second_time(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    await client.delete(f"/food-entries/{created['id']}", headers=headers)

    resp = await client.delete(f"/food-entries/{created['id']}", headers=headers)
    assert resp.status_code == 404


async def test_patch_after_delete_returns_404(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    await client.delete(f"/food-entries/{created['id']}", headers=headers)

    resp = await client.patch(f"/food-entries/{created['id']}", json=_BODY, headers=headers)
    assert resp.status_code == 404


async def test_delete_rejects_another_users_entry(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    other = await client.post(
        "/auth/sign-up",
        json={"email": "deleter@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.delete(f"/food-entries/{created['id']}", headers=other_headers)
    assert resp.status_code == 404


async def test_post_with_the_client_id_of_a_deleted_entry_returns_404_not_200(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()
    await client.delete(f"/food-entries/{created['id']}", headers=headers)

    resp = await client.post("/food-entries", json=_BODY, headers=headers)

    assert resp.status_code == 404


async def test_list_excludes_entries_outside_the_range(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/food-entries", json=_BODY, headers=headers)).json()

    resp = await client.get(
        "/food-entries", params={"from": "2020-01-01", "to": "2020-01-02"}, headers=headers
    )

    assert resp.status_code == 200
    assert resp.json() == []
