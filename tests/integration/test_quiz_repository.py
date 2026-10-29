"""SQLAlchemyQuizRepository.get_or_add_daily: both branches of the insert-or-read."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.entities.quiz import Quiz
from src.domain.entities.user import User
from src.domain.enums import QuizKind
from src.infrastructure.db.base import Base
import src.infrastructure.db.models  # noqa: F401 — registers every table
from src.infrastructure.db.models.quiz_question_model import QuizQuestionORM
from src.infrastructure.db.models.quiz_topic_model import QuizTopicORM
from src.infrastructure.db.repositories.quiz_repository import SQLAlchemyQuizRepository
from src.infrastructure.db.repositories.user_repository import SQLAlchemyUserRepository

DAY = date(2026, 1, 15)


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as s:
        yield s
    await engine.dispose()


async def _bank(session) -> list:
    topic = QuizTopicORM(id=uuid4(), slug="t", label="T", active=True)
    session.add(topic)
    await session.flush()
    rows = [
        QuizQuestionORM(
            id=uuid4(),
            topic_id=topic.id,
            text=f"q{i}",
            options=[{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
            correct_option_id="a",
            explanation="e",
            active=True,
        )
        for i in range(10)
    ]
    session.add_all(rows)
    await session.flush()
    return [r.to_domain() for r in rows]


async def test_fresh_insert_returns_the_passed_quiz_without_a_second_read(session, monkeypatch):
    user = await SQLAlchemyUserRepository(session).create(User.create(email="q@example.com"))
    questions = await _bank(session)
    repo = SQLAlchemyQuizRepository(session)

    async def _no_read(*_a, **_k):
        raise AssertionError("fresh insert must not re-read the quiz")

    monkeypatch.setattr(repo, "get_daily", _no_read)
    quiz = Quiz.create(user.id, QuizKind.DAILY, DAY, questions[:5])

    assert await repo.get_or_add_daily(quiz) is quiz
    monkeypatch.undo()
    stored = await repo.get_daily(user.id, DAY)
    assert stored.id == quiz.id
    assert [q.id for q in stored.questions] == [q.id for q in quiz.questions]


async def test_conflict_returns_the_stored_quiz_not_the_passed_one(session):
    user = await SQLAlchemyUserRepository(session).create(User.create(email="q@example.com"))
    questions = await _bank(session)
    repo = SQLAlchemyQuizRepository(session)
    first = Quiz.create(user.id, QuizKind.DAILY, DAY, questions[:5])
    await repo.get_or_add_daily(first)

    loser = Quiz.create(user.id, QuizKind.DAILY, DAY, questions[5:])
    got = await repo.get_or_add_daily(loser)

    assert got.id == first.id != loser.id
    assert [q.id for q in got.questions] == [q.id for q in first.questions]
