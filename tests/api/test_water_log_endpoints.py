"""GET /water-logs — end-to-end against the real app."""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities.water_log import WaterLog
from src.infrastructure.db.models.water_log_model import WaterLogORM
from src.infrastructure.db.session import engine


async def test_returns_empty_list_in_a_given_range(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get(
        "/water-logs", params={"from": "2026-01-01", "to": "2026-01-31"}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_requires_auth(client):
    resp = await client.get("/water-logs", params={"from": "2026-01-01", "to": "2026-01-31"})
    assert resp.status_code == 401


async def test_returns_the_seeded_log_with_camel_case_shape(client, signed_up):
    user_id = signed_up["user"]["id"]
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        session.add(
            WaterLogORM.from_domain(WaterLog.create(user_id, 350, logged_on=date(2026, 1, 15)))
        )
        await session.commit()

    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.get(
        "/water-logs", params={"from": "2026-01-01", "to": "2026-01-31"}, headers=headers
    )

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    log = body[0]
    assert set(log.keys()) == {"id", "userId", "amountMl", "loggedAt", "loggedOn"}
    assert log["userId"] == user_id
    assert log["amountMl"] == 350
    assert log["loggedOn"] == "2026-01-15"
