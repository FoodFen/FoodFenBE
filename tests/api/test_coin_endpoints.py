"""GET /quests and POST /coins/redeem — end-to-end against the real app + DB."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.entities.food_entry import FoodEntry
from src.domain.enums import CoinReason, InputMethod, MealType, QuestCadence, QuestType
from src.infrastructure.db.models.coin_transaction_model import CoinTransactionORM
from src.infrastructure.db.models.food_entry_model import FoodEntryORM
from src.infrastructure.db.models.quest_definition_model import QuestDefinitionORM
from src.infrastructure.db.session import engine

DAY = date(2026, 9, 30)  # a Wednesday; its week starts Monday 2026-09-28


async def _add(*rows) -> None:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add_all(rows)
        await session.commit()


def _definition(
    quest_type, target, reward, cadence=QuestCadence.DAILY, ratio=1.0
) -> QuestDefinitionORM:
    return QuestDefinitionORM(
        id=uuid4(), quest_type=quest_type, target=target, reward_coins=reward,
        cadence=cadence, completion_ratio=ratio, active=True,
    )


def _meal(user_id, meal_type, day=DAY) -> FoodEntryORM:
    return FoodEntryORM.from_domain(
        FoodEntry.create(
            user_id, "meal", InputMethod.MANUAL, 400, 50.0, 20.0, 10.0, meal_type,
            client_id=uuid4().hex, logged_on=day,
        )
    )


@pytest_asyncio.fixture
async def auth(signed_up):
    return {"Authorization": f"Bearer {signed_up['accessToken']}"}, signed_up["user"]["id"]


async def test_quests_require_auth(client):
    assert (await client.get("/quests", params={"date": "2026-09-30"})).status_code == 401


async def test_quest_is_issued_at_zero_progress_then_paid_once_when_achieved(client, auth):
    headers, user_id = auth
    await _add(_definition(QuestType.LOG_BREAKFAST, 1, 10))

    first = (await client.get("/quests", params={"date": DAY.isoformat()}, headers=headers)).json()
    assert first["balance"] == 0
    assert first["quests"][0] | {"id": None} == {
        "id": None, "questType": "log_breakfast", "cadence": "daily", "questDate": "2026-09-30",
        "progress": 0, "target": 1, "rewardCoins": 10, "completed": False,
        "completionRatio": 1.0,
    }

    await _add(_meal(user_id, MealType.BREAKFAST))
    for _ in range(2):  # the second read must not pay again
        body = (await client.get("/quests", params={"date": DAY.isoformat()}, headers=headers)).json()
        assert body["balance"] == 10
        assert body["quests"][0]["completed"] is True


async def test_quest_exposes_its_completion_ratio(client, auth):
    headers, _ = auth
    await _add(_definition(QuestType.HIT_CALORIE_GOAL, 100, 20, ratio=0.9))
    body = (await client.get("/quests", params={"date": DAY.isoformat()}, headers=headers)).json()
    assert body["quests"][0]["completionRatio"] == 0.9


async def test_weekly_quest_is_keyed_on_monday_and_counts_distinct_days(client, auth):
    headers, user_id = auth
    await _add(
        _definition(QuestType.STAY_ACTIVE_WEEK, 2, 50, QuestCadence.WEEKLY),
        _meal(user_id, MealType.LUNCH, date(2026, 9, 28)),
        _meal(user_id, MealType.DINNER, date(2026, 9, 28)),  # same day: counts once
        _meal(user_id, MealType.LUNCH, date(2026, 9, 29)),
        _meal(user_id, MealType.LUNCH, date(2026, 9, 27)),  # previous week: ignored
    )
    body = (await client.get("/quests", params={"date": DAY.isoformat()}, headers=headers)).json()
    quest = body["quests"][0]
    assert (quest["questDate"], quest["progress"], quest["completed"]) == ("2026-09-28", 2, True)
    assert body["balance"] == 50


async def test_redeem_needs_enough_coins_then_grants_premium_days(client, auth):
    headers, user_id = auth
    resp = await client.post("/coins/redeem", json={"days": 10}, headers=headers)
    assert resp.status_code == 409

    await _add(CoinTransactionORM.from_domain(CoinTransaction.create(user_id, 700, CoinReason.ADJUSTMENT)))
    resp = await client.post("/coins/redeem", json={"days": 10}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["balance"] == 100
    sub = body["subscription"]
    assert (sub["planType"], sub["status"]) == ("coin_redeem", "active")
    assert date.fromisoformat(sub["endDate"]) == date.today() + timedelta(days=9)

    me = (await client.get("/subscriptions/me", headers=headers)).json()
    assert me["hasActiveSubscription"] is True
    assert (await client.get("/auth/me", headers=headers)).json()["subscriptionTier"] == "premium"


async def test_redeem_rejects_an_unknown_bundle(client, auth):
    headers, _ = auth
    assert (await client.post("/coins/redeem", json={"days": 7}, headers=headers)).status_code == 400


async def test_checkout_cannot_buy_the_coin_plan(client, auth):
    headers, _ = auth
    resp = await client.post("/payments/checkout", json={"planType": "coin_redeem"}, headers=headers)
    assert resp.status_code == 422
