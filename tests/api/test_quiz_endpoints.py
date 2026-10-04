"""Quiz endpoints — end-to-end against the real app + DB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.domain.enums import CoinReason
from src.infrastructure.db.models.coin_transaction_model import CoinTransactionORM
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


def _answers(quiz: dict, option: str = "a", wrong: int = 0) -> dict:
    """Answer every question with ``option``; the first ``wrong`` ones with "b" instead."""
    return {
        "answers": [
            {"questionId": q["id"], "optionId": "b" if i < wrong else option}
            for i, q in enumerate(quiz["questions"])
        ]
    }


async def _submit(client, headers, quiz: dict, body: dict | None = None):
    return await client.post(
        f"/quizzes/{quiz['id']}/submit", json=body or _answers(quiz), headers=headers
    )


async def _ledger():
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        return list((await session.execute(select(CoinTransactionORM))).scalars())


async def test_submit_requires_auth(client):
    resp = await client.post(f"/quizzes/{uuid4()}/submit", json={"answers": []})
    assert resp.status_code == 401


async def test_submitting_a_daily_quiz_grades_it_and_pays_per_correct_answer(client, auth, bank):
    quiz = (await _daily(client, auth)).json()
    resp = await _submit(client, auth, quiz, _answers(quiz, wrong=1))
    assert resp.status_code == 200
    body = resp.json()
    assert (body["quizId"], body["correctCount"], body["total"]) == (quiz["id"], 4, 5)
    assert (body["coinsEarned"], body["balance"], body["coinsRemainingToday"]) == (16, 16, None)
    first = body["answers"][0]
    assert first["questionId"] == quiz["questions"][0]["id"]
    assert (first["selectedOptionId"], first["correctOptionId"], first["correct"]) == ("b", "a", False)
    assert first["explanation"].startswith("giải thích")
    [row] = await _ledger()
    assert (row.amount, row.reason) == (16, CoinReason.QUIZ_DAILY)


async def test_a_submitted_quiz_reads_back_as_completed_with_its_result(client, auth, bank):
    quiz = (await _daily(client, auth)).json()
    result = (await _submit(client, auth, quiz)).json()
    again = (await client.get(f"/quizzes/{quiz['id']}", headers=auth)).json()
    assert again["status"] == "completed" and again["result"] == result
    assert len(again["questions"]) == 5


async def test_submitting_twice_is_409_with_a_code_and_pays_once(client, auth, bank):
    quiz = (await _daily(client, auth)).json()
    assert (await _submit(client, auth, quiz)).status_code == 200
    again = await _submit(client, auth, quiz)
    assert again.status_code == 409
    assert again.json()["error"] == "quiz_already_submitted"
    assert [row.amount for row in await _ledger()] == [20]


async def test_malformed_answers_are_rejected_without_paying(client, auth, bank):
    quiz = (await _daily(client, auth)).json()
    ok = _answers(quiz)["answers"]
    bad_bodies = [
        {"answers": ok[:4]},  # one missing
        {"answers": [*ok[:4], {"questionId": str(uuid4()), "optionId": "a"}]},  # not this quiz's
        {"answers": [*ok[:4], {**ok[0]}]},  # one question twice
        _answers(quiz, option="z"),  # option the questions don't have
    ]
    for body in bad_bodies:
        assert (await _submit(client, auth, quiz, body)).status_code == 400
    assert await _ledger() == []
    assert (await _submit(client, auth, quiz)).status_code == 200  # still submittable


async def test_another_users_quiz_cannot_be_submitted(client, auth, bank):
    quiz = (await _daily(client, auth)).json()
    stranger = await _other_user_headers(client)
    assert (await _submit(client, stranger, quiz)).status_code == 404
    assert await _ledger() == []


async def test_practice_pays_one_coin_per_correct_answer_up_to_the_daily_cap(client, auth, bank):
    results = []
    for _ in range(3):
        quiz = (await _practice(client, auth)).json()
        results.append((await _submit(client, auth, quiz)).json())
    assert [(r["coinsEarned"], r["coinsRemainingToday"]) for r in results] == [(5, 5), (5, 0), (0, 0)]
    assert results[2]["correctCount"] == 5  # past the cap it still grades, it just pays nothing
    assert results[2]["balance"] == 10
    assert [row.amount for row in await _ledger()] == [5, 5]  # no zero-coin ledger line


async def test_practice_cap_is_per_the_quizs_own_date(client, auth, bank):
    for _ in range(2):  # spend today's cap
        quiz = (await _practice(client, auth)).json()
        await _submit(client, auth, quiz)
    yesterday = _today() - timedelta(days=1)
    quiz = (await _practice(client, auth, yesterday)).json()
    assert quiz["coinsRemainingToday"] == 10
    result = (await _submit(client, auth, quiz)).json()
    assert (result["coinsEarned"], result["balance"]) == (5, 15)


async def test_practice_quiz_started_before_the_cap_is_clipped_when_submitted(client, auth, bank):
    first, second, third = [(await _practice(client, auth)).json() for _ in range(3)]
    await _submit(client, auth, first)
    await _submit(client, auth, second)
    # `third` was issued while 10 coins were still available; the cap is applied at submit.
    assert third["coinsRemainingToday"] == 10
    assert (await _submit(client, auth, third)).json()["coinsEarned"] == 0
