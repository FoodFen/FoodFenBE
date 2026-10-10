"""Admin users / quizzes / quests lists and the dashboard's food + premium counts. End-to-end."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.entities.food_entry import FoodEntry
from src.domain.entities.streak import Streak
from src.domain.entities.subscription import Subscription
from src.domain.enums import InputMethod, MealType, PlanType, QuestCadence, QuestType, SubscriptionTier
from src.infrastructure.db.models.food_entry_model import FoodEntryORM
from src.infrastructure.db.models.quest_definition_model import QuestDefinitionORM
from src.infrastructure.db.models.quiz_question_model import QuizQuestionORM
from src.infrastructure.db.models.quiz_topic_model import QuizTopicORM
from src.infrastructure.db.models.streak_model import StreakORM
from src.infrastructure.db.models.subscription_model import SubscriptionORM
from src.infrastructure.db.models.user_model import UserORM
from src.infrastructure.db.session import engine

ROUTES = ["/admin/users", "/admin/quizzes", "/admin/quests"]


async def _add(*rows) -> None:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add_all(rows)
        await session.commit()


async def _make_premium(user_id: int) -> None:
    async with async_sessionmaker(engine)() as session:
        (await session.get(UserORM, user_id)).subscription_tier = SubscriptionTier.PREMIUM
        await session.commit()


def _vn_today():
    return datetime.now(timezone(timedelta(hours=7))).date()


@pytest.mark.parametrize("route", ROUTES)
async def test_non_admin_is_forbidden(client, make_user, route):
    headers, _ = await make_user("plain@example.com")
    assert (await client.get(route, headers=headers)).status_code == 403


async def test_users_row_shape_and_derived_fields(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, uid = await make_user("pro@example.com")
    await _make_premium(uid)
    today = _vn_today()
    await _add(
        SubscriptionORM.from_domain(
            Subscription.create(uid, PlanType.MONTHLY, today, today + timedelta(days=5), 99000)
        ),
        StreakORM.from_domain(
            Streak(id=uuid4(), user_id=uid, current_streak=3, longest_streak=3, last_active_date=today)
        ),
    )

    body = (await client.get("/admin/users?q=PRO", headers=admin)).json()
    assert body["total"] == 1 and body["nextCursor"] is None
    row = body["users"][0]
    assert set(row) == {"id", "displayName", "email", "role", "tier", "streak", "createdAt", "isActive"}
    assert (row["id"], row["email"], row["displayName"], row["role"], row["tier"], row["streak"], row["isActive"]) == (
        uid, "pro@example.com", "U", "user", "premium", 3, True,
    )


async def test_users_tier_filter_and_paging(client, make_user):
    admin, admin_id = await make_user("admin@example.com", admin=True)
    ids = [admin_id] + [(await make_user(f"u{i}@example.com"))[1] for i in range(3)]
    newest_first = sorted(ids, reverse=True)  # signups share a second at worst: id breaks the tie
    first = (await client.get("/admin/users?limit=3", headers=admin)).json()
    assert [u["id"] for u in first["users"]] == newest_first[:3]
    assert (first["total"], first["nextCursor"]) == (4, "3")
    last = (await client.get(f"/admin/users?limit=3&cursor={first['nextCursor']}", headers=admin)).json()
    assert ([u["id"] for u in last["users"]], last["nextCursor"]) == (newest_first[3:], None)
    assert (await client.get("/admin/users?tier=free", headers=admin)).json()["total"] == 4
    assert (await client.get("/admin/users?tier=premium", headers=admin)).json()["total"] == 0


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "cursor=abc", "cursor=-1", "tier=gold", f"q={'x' * 101}"])
async def test_users_bad_params_are_422(client, make_user, query):
    admin, _ = await make_user("admin@example.com", admin=True)
    assert (await client.get(f"/admin/users?{query}", headers=admin)).status_code == 422


async def test_quizzes_lists_inactive_too_ordered_by_topic_then_text(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    zed, alpha = QuizTopicORM(id=uuid4(), slug="z", label="Zed"), QuizTopicORM(id=uuid4(), slug="a", label="Alpha")
    await _add(zed, alpha)
    opts = [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}]

    def question(topic, text, active):
        return QuizQuestionORM(
            id=uuid4(), topic_id=topic.id, text=text, options=opts, correct_option_id="a",
            explanation="e", active=active,
        )

    rows = [question(zed, "b?", True), question(alpha, "z?", False), question(alpha, "a?", True)]
    await _add(*rows)
    body = (await client.get("/admin/quizzes", headers=admin)).json()
    assert body == [
        {"id": str(rows[2].id), "question": "a?", "topic": "Alpha", "active": True},
        {"id": str(rows[1].id), "question": "z?", "topic": "Alpha", "active": False},
        {"id": str(rows[0].id), "question": "b?", "topic": "Zed", "active": True},
    ]


async def test_quests_lists_inactive_too_ordered_by_cadence_then_title(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)

    def definition(quest_type, title, cadence, active=True):
        return QuestDefinitionORM(
            id=uuid4(), quest_type=quest_type, target=3, reward_coins=7, cadence=cadence,
            completion_ratio=1.0, active=active, title_vi=title, title_en="t", description_vi="d",
            description_en="d",
        )

    rows = [
        definition(QuestType.LOG_WEIGHT, "Cân", QuestCadence.WEEKLY),
        definition(QuestType.DRINK_WATER, "Uống nước", QuestCadence.DAILY, active=False),
        definition(QuestType.LOG_BREAKFAST, "Ăn sáng", QuestCadence.DAILY),
    ]
    await _add(*rows)
    body = (await client.get("/admin/quests", headers=admin)).json()
    assert body == [
        {"id": str(rows[2].id), "title": "Ăn sáng", "target": 3, "rewardCoins": 7, "cadence": "daily", "active": True},
        {"id": str(rows[1].id), "title": "Uống nước", "target": 3, "rewardCoins": 7, "cadence": "daily", "active": False},
        {"id": str(rows[0].id), "title": "Cân", "target": 3, "rewardCoins": 7, "cadence": "weekly", "active": True},
    ]


async def test_dashboard_counts_live_food_entries_and_effective_premium(client, make_user):
    admin, _ = await make_user("admin@example.com", admin=True)
    _, uid = await make_user("pro@example.com")
    await _make_premium(uid)
    today = _vn_today()

    def meal(day, deleted=False):
        row = FoodEntryORM.from_domain(FoodEntry.create(
            uid, "m", InputMethod.MANUAL, 400, 50.0, 20.0, 10.0, MealType.LUNCH,
            client_id=uuid4().hex, logged_on=day,
        ))
        row.deleted_at = datetime.now(UTC) if deleted else None
        return row

    await _add(meal(today), meal(today), meal(today, deleted=True), meal(today - timedelta(days=1)))
    url = f"/admin/dashboard?from={today - timedelta(days=1)}&to={today}"
    body = (await client.get(url, headers=admin)).json()
    assert [d["foodEntries"] for d in body["daily"]] == [1, 2]
    assert (body["totals"]["foodEntries"], body["totals"]["premiumUsers"]) == (3, 1)
