"""GET /daily-goals — end-to-end against the real app."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities.daily_goal import DailyGoal
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM
from src.infrastructure.db.session import engine


async def test_returns_empty_list_for_a_new_user(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get("/daily-goals", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_requires_auth(client):
    resp = await client.get("/daily-goals")
    assert resp.status_code == 401


async def test_returns_the_seeded_goal_with_camel_case_shape(client, signed_up):
    user_id = signed_up["user"]["id"]
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add(
            DailyGoalORM.from_domain(
                DailyGoal.create(
                    user_id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1), client_id="goal_1"
                )
            )
        )
        await session.commit()

    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get("/daily-goals", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    goal = body[0]
    assert set(goal.keys()) == {
        "id",
        "userId",
        "targetKcal",
        "targetCarbsG",
        "targetProteinG",
        "targetFatG",
        "targetWaterMl",
        "effectiveDate",
    }
    assert goal["userId"] == user_id
    assert goal["targetKcal"] == 2000
    assert goal["effectiveDate"] == "2026-01-01"


_CREATE_BODY = {
    "targetKcal": 2000,
    "targetCarbsG": 200.0,
    "targetProteinG": 150.0,
    "targetFatG": 60.0,
    "targetWaterMl": 2500,
    "effectiveDate": "2026-01-01",
    "clientId": "goal_1",
}


async def test_post_creates_a_goal(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.post("/daily-goals", json=_CREATE_BODY, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["targetKcal"] == 2000


async def test_post_with_repeated_client_id_returns_the_same_goal(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    first = (await client.post("/daily-goals", json=_CREATE_BODY, headers=headers)).json()
    second = (await client.post("/daily-goals", json=_CREATE_BODY, headers=headers)).json()
    assert first["id"] == second["id"]


async def test_create_requires_auth(client):
    resp = await client.post("/daily-goals", json=_CREATE_BODY)
    assert resp.status_code == 401
