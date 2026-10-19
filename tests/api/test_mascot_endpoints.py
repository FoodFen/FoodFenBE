"""GET /mascots, POST /mascots/{id}/purchase, PUT /mascots/equipped — end-to-end against the real app + DB."""

from __future__ import annotations

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.enums import CoinReason
from src.infrastructure.db.models.coin_transaction_model import CoinTransactionORM
from src.infrastructure.db.models.mascot_model import MascotORM
from src.infrastructure.db.session import engine


async def _add(*rows) -> None:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add_all(rows)
        await session.commit()


async def _credit(user_id: int, amount: int) -> None:
    await _add(CoinTransactionORM.from_domain(CoinTransaction.create(user_id, amount, CoinReason.ADJUSTMENT)))


@pytest_asyncio.fixture
async def auth(signed_up):
    # "default" is seeded for every test schema (tests/conftest.py); add the paid ones.
    await _add(
        MascotORM(id="berry", name="Berry", coin_cost=600, active=True),
        MascotORM(id="sprout", name="Sprout", coin_cost=300, active=True),
        MascotORM(id="retired", name="Retired", coin_cost=100, active=False),
    )
    return {"Authorization": f"Bearer {signed_up['accessToken']}"}, signed_up["user"]["id"]


def _owned(body: dict) -> dict[str, bool]:
    return {m["id"]: m["owned"] for m in body["mascots"]}


async def test_fresh_user_owns_and_equips_only_the_free_mascot(client, auth):
    headers, _ = auth
    resp = await client.get("/mascots", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "balance": 0,
        "equippedId": "default",
        "mascots": [  # ordered by coinCost, inactive ones not listed
            {"id": "default", "name": "Fen", "coinCost": 0, "owned": True},
            {"id": "sprout", "name": "Sprout", "coinCost": 300, "owned": False},
            {"id": "berry", "name": "Berry", "coinCost": 600, "owned": False},
        ],
    }


async def test_purchase_debits_coins_flips_owned_and_writes_a_spend_row(client, auth):
    headers, user_id = auth
    await _credit(user_id, 500)
    resp = await client.post("/mascots/sprout/purchase", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance"] == 200
    assert body["equippedId"] == "default"  # buying doesn't equip
    assert _owned(body) == {"default": True, "sprout": True, "berry": False}

    assert (await client.get("/mascots", headers=headers)).json() == body
    async with async_sessionmaker(engine)() as session:
        spend = (
            await session.scalars(select(CoinTransactionORM).where(CoinTransactionORM.reason == CoinReason.SPEND))
        ).all()
    assert [(t.user_id, t.amount) for t in spend] == [(user_id, -300)]


async def test_purchase_with_too_few_coins_is_409_and_changes_nothing(client, auth):
    headers, user_id = auth
    await _credit(user_id, 299)
    resp = await client.post("/mascots/sprout/purchase", headers=headers)
    assert resp.status_code == 409
    assert "error" not in resp.json()  # plain message, like redeem
    body = (await client.get("/mascots", headers=headers)).json()
    assert body["balance"] == 299
    assert _owned(body)["sprout"] is False


async def test_purchasing_an_owned_or_free_mascot_is_409_mascot_already_owned(client, auth):
    headers, user_id = auth
    await _credit(user_id, 1000)
    assert (await client.post("/mascots/sprout/purchase", headers=headers)).status_code == 200
    for mascot_id in ("sprout", "default"):
        resp = await client.post(f"/mascots/{mascot_id}/purchase", headers=headers)
        assert resp.status_code == 409
        assert resp.json()["error"] == "mascot_already_owned"
    assert (await client.get("/mascots", headers=headers)).json()["balance"] == 700  # charged once


async def test_purchasing_an_unknown_or_inactive_mascot_is_404(client, auth):
    headers, user_id = auth
    await _credit(user_id, 1000)
    for mascot_id in ("nope", "retired"):
        assert (await client.post(f"/mascots/{mascot_id}/purchase", headers=headers)).status_code == 404


async def test_equip_an_owned_mascot_is_reflected_by_get(client, auth):
    headers, user_id = auth
    await _credit(user_id, 300)
    await client.post("/mascots/sprout/purchase", headers=headers)
    for _ in range(2):  # re-equipping the current one is a 200 no-op
        resp = await client.put("/mascots/equipped", json={"mascotId": "sprout"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json() == {"equippedId": "sprout"}
    assert (await client.get("/mascots", headers=headers)).json()["equippedId"] == "sprout"

    back = await client.put("/mascots/equipped", json={"mascotId": "default"}, headers=headers)
    assert back.json() == {"equippedId": "default"}  # the free one is always equippable


async def test_equipping_a_mascot_that_is_not_owned_is_409_mascot_not_owned(client, auth):
    headers, _ = auth
    resp = await client.put("/mascots/equipped", json={"mascotId": "berry"}, headers=headers)
    assert resp.status_code == 409
    assert resp.json()["error"] == "mascot_not_owned"
    assert (await client.get("/mascots", headers=headers)).json()["equippedId"] == "default"


async def test_equipping_an_unknown_or_inactive_mascot_is_404(client, auth):
    headers, _ = auth
    for mascot_id in ("nope", "retired"):
        resp = await client.put("/mascots/equipped", json={"mascotId": mascot_id}, headers=headers)
        assert resp.status_code == 404


async def test_a_deactivated_equipped_mascot_reads_as_default(client, auth):
    headers, user_id = auth
    await _credit(user_id, 300)
    await client.post("/mascots/sprout/purchase", headers=headers)
    await client.put("/mascots/equipped", json={"mascotId": "sprout"}, headers=headers)
    async with async_sessionmaker(engine)() as session:
        (await session.get(MascotORM, "sprout")).active = False
        await session.commit()
    body = (await client.get("/mascots", headers=headers)).json()
    assert body["equippedId"] == "default"
    assert "sprout" not in _owned(body)


async def test_mascot_endpoints_require_auth(client):
    assert (await client.get("/mascots")).status_code == 401
    assert (await client.post("/mascots/sprout/purchase")).status_code == 401
    assert (await client.put("/mascots/equipped", json={"mascotId": "sprout"})).status_code == 401
