"""Quiz endpoints — end-to-end against the real app + DB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest_asyncio
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.infrastructure.db.models.quiz_question_model import QuizQuestionORM
from src.infrastructure.db.models.quiz_topic_model import QuizTopicORM
from src.infrastructure.db.session import engine


def _today():
    return datetime.now(UTC).date()


async def _add(*rows) -> None:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        session.add_all(rows)
        await session.commit()


def _topic(slug: str = "macros", label: str = "Đạm, tinh bột và chất béo", active: bool = True):
    return QuizTopicORM(id=uuid4(), slug=slug, label=label, active=active)


def _questions(topic: QuizTopicORM, n: int = 6) -> list[QuizQuestionORM]:
    """Every question's correct option is "a"."""
    return [
        QuizQuestionORM(
            id=uuid4(),
            topic_id=topic.id,
            text=f"{topic.slug} câu {i}",
            options=[{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            correct_option_id="a",
            explanation=f"giải thích {i}",
            active=True,
        )
        for i in range(n)
    ]


async def _seed(topic: QuizTopicORM, n: int = 6) -> None:
    """Topic first, questions second: the models have no relationship(), so the ORM would not
    order the two inserts for the foreign key."""
    await _add(topic)
    await _add(*_questions(topic, n))


@pytest_asyncio.fixture
async def bank():
    topic = _topic()
    await _seed(topic)
    return topic


@pytest_asyncio.fixture
async def auth(signed_up):
    return {"Authorization": f"Bearer {signed_up['accessToken']}"}


async def _other_user_headers(client) -> dict:
    resp = await client.post(
        "/auth/sign-up",
        json={"email": "other@example.com", "password": "s3cret-pass", "displayName": "Other"},
    )
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


async def _daily(client, headers, day=None):
    return await client.get(
        "/quizzes/daily", params={"date": (day or _today()).isoformat()}, headers=headers
    )


async def _practice(client, headers, day=None, topic="macros"):
    return await client.post(
        "/quizzes/practice",
        json={"topic": topic, "date": (day or _today()).isoformat()},
        headers=headers,
    )


async def test_quiz_endpoints_require_auth(client):
    day = _today().isoformat()
    assert (await client.get("/quizzes/topics")).status_code == 401
    assert (await client.get("/quizzes/daily", params={"date": day})).status_code == 401
    assert (await client.post("/quizzes/practice", json={"topic": "x", "date": day})).status_code == 401
    assert (await client.get(f"/quizzes/{uuid4()}")).status_code == 401


async def test_topics_lists_only_active_topics(client, auth, bank):
    await _add(_topic("old", "Cũ", active=False))
    resp = await client.get("/quizzes/topics", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == {"topics": [{"id": "macros", "label": "Đạm, tinh bột và chất béo"}]}


async def test_daily_quiz_is_created_once_and_never_reveals_answers(client, auth, bank):
    first = (await _daily(client, auth)).json()
    again = (await _daily(client, auth)).json()
    assert first["id"] == again["id"]
    assert (first["kind"], first["topic"], first["date"]) == ("daily", None, _today().isoformat())
    assert (first["coinsPerCorrect"], first["coinsRemainingToday"]) == (4, None)
    assert (first["status"], first["result"]) == ("available", None)
    assert len(first["questions"]) == 5
    for question in first["questions"]:
        assert set(question) == {"id", "text", "options"}
        assert all(set(option) == {"id", "text"} for option in question["options"])


async def test_daily_quizzes_are_per_user_and_per_day(client, auth, bank):
    mine = (await _daily(client, auth)).json()
    other = (await _daily(client, await _other_user_headers(client))).json()
    tomorrow = (await _daily(client, auth, _today() + timedelta(days=1))).json()
    assert len({mine["id"], other["id"], tomorrow["id"]}) == 3


async def test_dates_outside_the_window_are_rejected(client, auth, bank):
    far = _today() + timedelta(days=2)
    assert (await _daily(client, auth, far)).status_code == 400
    assert (await _practice(client, auth, far)).status_code == 400
    assert (await _daily(client, auth, _today() - timedelta(days=2))).status_code == 400


async def test_practice_creates_a_fresh_quiz_each_call(client, auth, bank):
    first = (await _practice(client, auth)).json()
    second = (await _practice(client, auth)).json()
    assert first["id"] != second["id"]
    assert (first["kind"], first["topic"]) == ("practice", "macros")
    assert (first["coinsPerCorrect"], first["coinsRemainingToday"]) == (1, 10)
    assert first["date"] == _today().isoformat()


async def test_practice_on_an_unknown_topic_is_404(client, auth, bank):
    assert (await _practice(client, auth, topic="nope")).status_code == 404


async def test_practice_on_a_topic_with_too_few_questions_is_400(client, auth, bank):
    thin = _topic("thin", "Ít câu")
    await _seed(thin, n=3)
    assert (await _practice(client, auth, topic="thin")).status_code == 400


async def test_get_quiz_returns_own_quiz_and_hides_other_users_quizzes(client, auth, bank):
    quiz = (await _practice(client, auth)).json()
    own = await client.get(f"/quizzes/{quiz['id']}", headers=auth)
    assert own.status_code == 200 and own.json() == quiz
    stranger = await _other_user_headers(client)
    assert (await client.get(f"/quizzes/{quiz['id']}", headers=stranger)).status_code == 404
    assert (await client.get(f"/quizzes/{uuid4()}", headers=auth)).status_code == 404


async def test_an_issued_quiz_survives_a_question_being_deactivated(client, auth, bank):
    quiz = (await _practice(client, auth)).json()
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await session.execute(update(QuizQuestionORM).values(active=False))
        await session.commit()
    again = await client.get(f"/quizzes/{quiz['id']}", headers=auth)
    assert again.status_code == 200 and len(again.json()["questions"]) == 5
