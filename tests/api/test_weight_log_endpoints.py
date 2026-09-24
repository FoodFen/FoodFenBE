"""GET /weight-logs — end-to-end against the real app."""

from __future__ import annotations


async def test_returns_empty_list_in_a_given_range(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get(
        "/weight-logs", params={"from": "2026-01-01", "to": "2026-01-31"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_requires_auth(client):
    resp = await client.get("/weight-logs", params={"from": "2026-01-01", "to": "2026-01-31"})
    assert resp.status_code == 401
