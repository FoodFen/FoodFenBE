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
                DailyGoal.create(user_id, 2000, 200.0, 150.0, 60.0, 2500, date(2026, 1, 1))
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
