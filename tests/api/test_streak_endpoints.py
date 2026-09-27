"""POST /streak — end-to-end against the real app."""

from __future__ import annotations

_BODY = {"currentStreak": 3, "longestStreak": 5, "lastActiveDate": "2026-01-15"}


async def test_post_creates_the_streak(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.post("/streak", json=_BODY, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "id",
        "userId",
        "currentStreak",
        "longestStreak",
        "lastActiveDate",
    }
    assert body["currentStreak"] == 3
    assert body["longestStreak"] == 5
    assert body["lastActiveDate"] == "2026-01-15"


async def test_post_requires_auth(client):
    resp = await client.post("/streak", json=_BODY)
    assert resp.status_code == 401


async def test_post_again_replaces_the_same_row_not_a_new_one(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    first = (await client.post("/streak", json=_BODY, headers=headers)).json()

    second = (
        await client.post(
            "/streak",
            json={"currentStreak": 4, "longestStreak": 5, "lastActiveDate": "2026-01-16"},
            headers=headers,
        )
    ).json()

    assert second["id"] == first["id"]
    assert second["currentStreak"] == 4


async def test_post_accepts_a_null_last_active_date(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.post(
        "/streak",
        json={"currentStreak": 0, "longestStreak": 0, "lastActiveDate": None},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["lastActiveDate"] is None
