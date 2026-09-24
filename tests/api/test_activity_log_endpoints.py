"""GET /activity-logs — end-to-end against the real app."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities.activity_log import ActivityLog
from src.infrastructure.db.models.activity_log_model import ActivityLogORM
from src.infrastructure.db.session import engine


async def test_returns_empty_list_in_a_given_range(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get(
        "/activity-logs", params={"from": "2026-01-01", "to": "2026-01-31"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_requires_from_and_to_query_params(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get("/activity-logs", headers=headers)
    assert resp.status_code == 422


async def test_requires_auth(client):
    resp = await client.get(
        "/activity-logs", params={"from": "2026-01-01", "to": "2026-01-31"}
    )
    assert resp.status_code == 401


async def test_returns_the_seeded_log_with_camel_case_shape(client, signed_up):
    user_id = signed_up["user"]["id"]
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add(
            ActivityLogORM.from_domain(
                ActivityLog.create(
                    user_id, "running", 320, client_id="activity_1", logged_on=date(2026, 1, 15)
                )
            )
        )
        await session.commit()

    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get(
        "/activity-logs", params={"from": "2026-01-01", "to": "2026-01-31"}, headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    log = body[0]
    assert set(log.keys()) == {
        "id",
        "userId",
        "activityType",
        "caloriesBurned",
        "source",
        "loggedAt",
        "loggedOn",
    }
    assert log["userId"] == user_id
    assert log["activityType"] == "running"
    assert log["caloriesBurned"] == 320
    assert log["source"] == "manual"
    assert log["loggedOn"] == "2026-01-15"


_CREATE_BODY = {
    "activityType": "running",
    "caloriesBurned": 300,
    "clientId": "activity_1",
    "loggedOn": "2026-01-15",
}


async def test_post_creates_a_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["activityType"] == "running"


async def test_post_with_repeated_client_id_returns_the_same_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    first = (await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)).json()
    second = (await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)).json()
    assert first["id"] == second["id"]


async def test_post_stores_the_submitted_logged_at_not_the_servers_clock(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    body = {**_CREATE_BODY, "clientId": "activity_2", "loggedAt": "2026-01-15T08:00:00Z"}

    resp = await client.post("/activity-logs", json=body, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["loggedAt"].startswith("2026-01-15T08:00:00")


async def test_patch_stores_the_submitted_logged_at(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)).json()

    resp = await client.patch(
        f"/activity-logs/{created['id']}",
        json={
            "activityType": "swimming",
            "caloriesBurned": 450,
            "loggedAt": "2026-01-15T08:00:00Z",
            "loggedOn": "2026-01-15",
        },
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["loggedAt"].startswith("2026-01-15T08:00:00")


async def test_patch_replaces_the_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)).json()

    resp = await client.patch(
        f"/activity-logs/{created['id']}",
        json={"activityType": "swimming", "caloriesBurned": 450, "loggedOn": "2026-01-15"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["activityType"] == "swimming"


async def test_patch_rejects_another_users_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/activity-logs", json=_CREATE_BODY, headers=headers)).json()
    other = await client.post(
        "/auth/sign-up",
        json={"email": "other2@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.patch(
        f"/activity-logs/{created['id']}",
        json={"activityType": "x", "caloriesBurned": 1, "loggedOn": "2026-01-15"},
        headers=other_headers,
    )
    assert resp.status_code == 404
