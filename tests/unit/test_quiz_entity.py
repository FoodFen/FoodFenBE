"""Quiz entity unit tests: grading, invariants, date window, question picking. No I/O."""

from __future__ import annotations

import random
from datetime import date
from uuid import uuid4

import pytest

from src.domain.entities.quiz import (
    QUESTIONS_PER_QUIZ,
    Quiz,
    QuizOption,
    QuizQuestion,
    ensure_date_in_window,
    pick_questions,
)
from src.domain.enums import CoinReason, QuizKind
from src.domain.exceptions import (
    InvalidAttributeException,
    InvalidQuizAnswersException,
    InvalidQuizDateException,
)

TOPIC_ID = uuid4()


def _question(correct: str = "a") -> QuizQuestion:
    return QuizQuestion(
        id=uuid4(),
        topic_id=TOPIC_ID,
        text="q",
        options=[QuizOption("a", "A"), QuizOption("b", "B")],
        correct_option_id=correct,
        explanation="because",
    )


def _quiz() -> Quiz:
    return Quiz.create(1, QuizKind.DAILY, date(2026, 10, 3), [_question() for _ in range(5)])


def _all(quiz: Quiz, option: str) -> list[tuple]:
    return [(q.id, option) for q in quiz.questions]


def test_grade_counts_correct_answers():
    quiz = _quiz()
    answers = _all(quiz, "a")
    answers[0] = (answers[0][0], "b")
    assert quiz.grade(answers) == 4


def test_grade_requires_exactly_one_answer_per_question():
    quiz = _quiz()
    with pytest.raises(InvalidQuizAnswersException):
        quiz.grade(_all(quiz, "a")[:4])
    duplicated = _all(quiz, "a")
    duplicated[1] = duplicated[0]  # five answers, but one question answered twice
    with pytest.raises(InvalidQuizAnswersException):
        quiz.grade(duplicated)
    with pytest.raises(InvalidQuizAnswersException):
        quiz.grade([*_all(quiz, "a")[:4], (uuid4(), "a")])  # a question not in this quiz


def test_grade_rejects_an_option_the_question_does_not_have():
    quiz = _quiz()
    with pytest.raises(InvalidQuizAnswersException):
        quiz.grade(_all(quiz, "z"))


def test_quiz_needs_exactly_five_questions():
    with pytest.raises(InvalidAttributeException):
        Quiz.create(1, QuizKind.DAILY, date(2026, 10, 3), [_question() for _ in range(4)])


def test_question_correct_option_must_be_one_of_its_options():
    with pytest.raises(InvalidAttributeException):
        _question(correct="z")


def test_mark_submitted_records_the_grade_and_picks_the_ledger_reason():
    quiz = _quiz()
    quiz.mark_submitted(_all(quiz, "a"), 5, 20)
    assert quiz.submitted and (quiz.correct_count, quiz.coins_earned) == (5, 20)
    assert quiz.coin_reason is CoinReason.QUIZ_DAILY


def test_date_window_allows_yesterday_through_tomorrow_only():
    today = date(2026, 10, 3)
    for ok in (date(2026, 10, 2), today, date(2026, 10, 4)):
        ensure_date_in_window(ok, today)
    for bad in (date(2026, 10, 1), date(2026, 10, 5)):
        with pytest.raises(InvalidQuizDateException):
            ensure_date_in_window(bad, today)


def test_pick_prefers_unseen_questions_then_fills_from_seen():
    pool = [_question() for _ in range(8)]
    seen = {q.id for q in pool[:6]}  # only two unseen
    picked = pick_questions(pool, seen, rng=random.Random(0))
    assert len(picked) == QUESTIONS_PER_QUIZ == len({q.id for q in picked})
    assert {q.id for q in pool[6:]} <= {q.id for q in picked}  # both unseen ones made it in


def test_pick_with_a_small_pool_returns_what_exists():
    pool = [_question() for _ in range(3)]
    assert len(pick_questions(pool, set(), rng=random.Random(0))) == 3
