"""GET /daily-goals — end-to-end against the real app."""

from __future__ import annotations


async def test_returns_empty_list_for_a_new_user(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get("/daily-goals", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_requires_auth(client):
    resp = await client.get("/daily-goals")
    assert resp.status_code == 401
