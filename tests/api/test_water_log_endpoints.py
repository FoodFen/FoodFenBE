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
            WaterLogORM.from_domain(
                WaterLog.create(user_id, 350, client_id="water_1", logged_on=date(2026, 1, 15))
            )
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


_CREATE_BODY = {"amountMl": 350, "clientId": "water_1", "loggedOn": "2026-01-15"}


async def test_post_creates_a_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    resp = await client.post("/water-logs", json=_CREATE_BODY, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["amountMl"] == 350


async def test_post_with_repeated_client_id_returns_the_same_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    first = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()
    second = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()
    assert first["id"] == second["id"]


async def test_post_stores_the_submitted_logged_at_not_the_servers_clock(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    body = {**_CREATE_BODY, "clientId": "water_2", "loggedAt": "2026-01-15T08:00:00Z"}

    resp = await client.post("/water-logs", json=body, headers=headers)

    assert resp.status_code == 200
    assert resp.json()["loggedAt"].startswith("2026-01-15T08:00:00")


async def test_patch_replaces_the_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()

    resp = await client.patch(
        f"/water-logs/{created['id']}", json={"amountMl": 100}, headers=headers
    )

    assert resp.status_code == 200
    assert resp.json()["amountMl"] == 100


async def test_patch_rejects_another_users_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()
    other = await client.post(
        "/auth/sign-up",
        json={"email": "waterpatcher@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.patch(
        f"/water-logs/{created['id']}", json={"amountMl": 100}, headers=other_headers
    )
    assert resp.status_code == 404


async def test_patch_after_delete_returns_404(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()
    await client.delete(f"/water-logs/{created['id']}", headers=headers)

    resp = await client.patch(
        f"/water-logs/{created['id']}", json={"amountMl": 100}, headers=headers
    )
    assert resp.status_code == 404


async def test_delete_soft_deletes_and_it_disappears_from_list(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()

    resp = await client.delete(f"/water-logs/{created['id']}", headers=headers)
    assert resp.status_code == 204

    list_resp = await client.get(
        "/water-logs", params={"from": "2026-01-15", "to": "2026-01-15"}, headers=headers
    )
    assert list_resp.json() == []


async def test_delete_rejects_another_users_log(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()
    other = await client.post(
        "/auth/sign-up",
        json={"email": "waterother@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    other_headers = {"Authorization": f"Bearer {other.json()['accessToken']}"}

    resp = await client.delete(f"/water-logs/{created['id']}", headers=other_headers)
    assert resp.status_code == 404


async def test_post_with_the_client_id_of_a_deleted_log_returns_404_not_200(client, signed_up):
    headers = {"Authorization": f"Bearer {signed_up['accessToken']}"}
    created = (await client.post("/water-logs", json=_CREATE_BODY, headers=headers)).json()
    await client.delete(f"/water-logs/{created['id']}", headers=headers)

    resp = await client.post("/water-logs", json=_CREATE_BODY, headers=headers)

    assert resp.status_code == 404
