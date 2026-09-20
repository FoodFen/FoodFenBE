"""GET /users/{id} — behind auth. End-to-end against the real app + DB.

Not part of the front-end contract (it uses GET /auth/me for the caller's own
profile); this is an extra, kept for admin/dev lookup by id.
"""

from __future__ import annotations


def _auth(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['accessToken']}"}


async def test_get_user_requires_auth(client, signed_up):
    resp = await client.get("/users/999999")
    assert resp.status_code == 401


async def test_get_own_user_via_me_then_by_id(client, signed_up):
    me = await client.get("/auth/me", headers=_auth(signed_up))
    user_id = me.json()["id"]

    got = await client.get(f"/users/{user_id}", headers=_auth(signed_up))
    assert got.status_code == 200
    assert got.json()["id"] == user_id


async def test_get_missing_user_is_404_when_authed(client, signed_up):
    resp = await client.get("/users/999999", headers=_auth(signed_up))
    assert resp.status_code == 404
