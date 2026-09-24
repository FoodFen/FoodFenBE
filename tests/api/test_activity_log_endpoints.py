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
