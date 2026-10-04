"""GET /quests and POST /coins/redeem — end-to-end against the real app + DB."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.entities.food_entry import FoodEntry
from src.domain.enums import CoinReason, InputMethod, MealType, QuestCadence, QuestType
from src.infrastructure.db.models.coin_bundle_model import CoinBundleORM
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
        title_vi=f"{quest_type.value} vi", title_en=f"{quest_type.value} en",
        description_vi=f"{quest_type.value} mô tả vi",
        description_en=f"{quest_type.value} description en",
    )


def _bundle(days, cost, active=True) -> CoinBundleORM:
    return CoinBundleORM(id=uuid4(), days=days, coin_cost=cost, active=active)


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
        "completionRatio": 1.0, "unit": "count",
        "title": "log_breakfast vi", "description": "log_breakfast mô tả vi",
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
    await _add(_bundle(10, 600), _bundle(30, 1500))
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


async def test_quest_carries_its_unit_and_copy_in_the_requested_language(client, auth):
    headers, _ = auth
    await _add(_definition(QuestType.DRINK_WATER, 100, 10), _definition(QuestType.LOG_BREAKFAST, 1, 10))
    params = {"date": DAY.isoformat()}
    vi = (await client.get("/quests", params=params, headers=headers)).json()["quests"]
    by_type = {q["questType"]: q for q in vi}
    assert by_type["drink_water"]["unit"] == "percent"
    assert by_type["log_breakfast"]["unit"] == "count"
    assert (by_type["drink_water"]["title"], by_type["drink_water"]["description"]) == (
        "drink_water vi", "drink_water mô tả vi",
    )
    en = (await client.get("/quests", params={**params, "language": "en"}, headers=headers)).json()
    water = next(q for q in en["quests"] if q["questType"] == "drink_water")
    assert (water["title"], water["description"]) == ("drink_water en", "drink_water description en")


async def test_quests_reject_an_unsupported_language(client, auth):
    headers, _ = auth
    resp = await client.get("/quests", params={"date": DAY.isoformat(), "language": "fr"}, headers=headers)
    assert resp.status_code == 422


async def test_redeem_still_requires_auth(client):
    assert (await client.post("/coins/redeem", json={"days": 10})).status_code == 401


async def test_bundles_are_public_and_list_active_bundles_by_days_with_real_ids(client):
    await _add(_bundle(30, 1500), _bundle(10, 600), _bundle(7, 100, active=False))
    resp = await client.get("/coins/bundles")  # no Authorization header
    assert resp.status_code == 200
    bundles = resp.json()["bundles"]
    assert [(b["days"], b["coinCost"]) for b in bundles] == [(10, 600), (30, 1500)]
    assert all(UUID(b["id"]) for b in bundles)


async def test_redeem_charges_the_price_stored_in_the_bundle_row(client, auth):
    headers, user_id = auth
    await _add(_bundle(10, 250))
    await _add(CoinTransactionORM.from_domain(CoinTransaction.create(user_id, 300, CoinReason.ADJUSTMENT)))
    resp = await client.post("/coins/redeem", json={"days": 10}, headers=headers)
    assert (resp.status_code, resp.json()["balance"]) == (200, 50)


async def test_an_inactive_bundle_cannot_be_redeemed(client, auth):
    headers, user_id = auth
    await _add(_bundle(10, 100, active=False))
    await _add(CoinTransactionORM.from_domain(CoinTransaction.create(user_id, 700, CoinReason.ADJUSTMENT)))
    assert (await client.post("/coins/redeem", json={"days": 10}, headers=headers)).status_code == 400


async def test_redeem_rejects_an_unknown_bundle(client, auth):
    headers, _ = auth
    assert (await client.post("/coins/redeem", json={"days": 7}, headers=headers)).status_code == 400


async def test_checkout_cannot_buy_the_coin_plan(client, auth):
    headers, _ = auth
    resp = await client.post("/payments/checkout", json={"planType": "coin_redeem"}, headers=headers)
    assert resp.status_code == 422
