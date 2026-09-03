"""GET /users/{id} — now behind auth. End-to-end against the real app + DB."""

from __future__ import annotations


def _auth(tokens: dict) -> dict:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def test_get_user_requires_auth(client, registered):
    resp = await client.get("/users/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401


async def test_get_own_user_via_me_then_by_id(client, registered):
    me = await client.get("/auth/me", headers=_auth(registered))
    user_id = me.json()["id"]

    got = await client.get(f"/users/{user_id}", headers=_auth(registered))
    assert got.status_code == 200
    assert got.json()["id"] == user_id


async def test_get_missing_user_is_404_when_authed(client, registered):
    resp = await client.get(
        "/users/00000000-0000-0000-0000-000000000000", headers=_auth(registered)
    )
    assert resp.status_code == 404
