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
from src.domain.entities.quiz import QuizTopic
from src.domain.exceptions import (
    InvalidAttributeException,
    InvalidQuizAnswersException,
    InvalidQuizDateException,
    InvalidQuizQuestionException,
    InvalidQuizTopicException,
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


def _opts(*ids: str) -> list[QuizOption]:
    return [QuizOption(i, i.upper()) for i in ids]


def _create(**over):
    args = dict(
        topic_id=TOPIC_ID, text="q?", options=_opts("a", "b"), correct_option_id="a", explanation="because"
    )
    return QuizQuestion.create(**{**args, **over})


@pytest.mark.parametrize(
    ("over", "code", "field"),
    [
        ({"text": "  "}, "text_required", "text"),
        ({"text": "x" * 501}, "text_too_long", "text"),
        ({"options": _opts("a")}, "option_count", "options"),
        ({"options": _opts("a", "b", "c", "d", "e")}, "option_count", "options"),
        ({"options": _opts("a", "a")}, "option_ids_not_unique", "options"),
        ({"options": [QuizOption("", "A"), QuizOption("b", "B")], "correct_option_id": "b"}, "option_id_invalid", "options"),
        ({"options": [QuizOption("x" * 17, "A"), QuizOption("b", "B")], "correct_option_id": "b"}, "option_id_invalid", "options"),
        ({"options": [QuizOption("a", "A"), QuizOption("b", " ")]}, "option_text_required", "options.1.text"),
        ({"options": [QuizOption("a", "x" * 201), QuizOption("b", "B")]}, "option_text_too_long", "options.0.text"),
        ({"correct_option_id": "z"}, "correct_option_invalid", "correct_option_id"),
        ({"explanation": "x" * 1001}, "explanation_too_long", "explanation"),
    ],
)
def test_question_validation_codes(over, code, field):
    with pytest.raises(InvalidQuizQuestionException) as err:
        _create(**over)
    assert (err.value.code, err.value.field) == (code, field)


def test_question_create_trims_and_allows_an_empty_explanation():
    q = _create(text="  hi  ", options=[QuizOption("a", " A "), QuizOption("b", "B")], explanation="  ")
    assert (q.text, q.options[0].text, q.explanation, q.active) == ("hi", "A", "", True)


def test_question_update_changes_only_given_fields_and_validates_before_mutating():
    q = _create()
    q.update(text="new", active=False)
    assert (q.text, q.active, q.correct_option_id, len(q.options)) == ("new", False, "a", 2)
    with pytest.raises(InvalidQuizQuestionException):
        q.update(text="fine", correct_option_id="z")
    assert q.text == "new"  # nothing changed by the failed update
    q.update(options=_opts("a", "b", "c"), correct_option_id="c")
    assert [o.id for o in q.options] == ["a", "b", "c"] and q.correct_option_id == "c"


@pytest.mark.parametrize(
    ("slug", "label", "code", "field"),
    [
        ("Macros", "L", "invalid_slug", "slug"),
        ("a_b", "L", "invalid_slug", "slug"),
        ("-a", "L", "invalid_slug", "slug"),
        ("a--b", "L", "invalid_slug", "slug"),
        ("", "L", "invalid_slug", "slug"),
        ("a" * 33, "L", "invalid_slug", "slug"),
        ("ok", "  ", "label_required", "label"),
        ("ok", "x" * 65, "label_too_long", "label"),
    ],
)
def test_topic_validation_codes(slug, label, code, field):
    with pytest.raises(InvalidQuizTopicException) as err:
        QuizTopic.create(slug, label)
    assert (err.value.code, err.value.field) == (code, field)


def test_topic_create_trims_the_label_and_defaults_active():
    topic = QuizTopic.create("vitamins-minerals", "  Vitamin  ")
    assert (topic.slug, topic.label, topic.active) == ("vitamins-minerals", "Vitamin", True)


_LEGACY = [
    ({"options": _opts("a", "b", "c", "d", "e")}, "option_count"),
    ({"options": [QuizOption("a", "A"), QuizOption("b", " ")]}, "option_text_required"),
    ({"explanation": "x" * 2000}, "explanation_too_long"),
]


@pytest.mark.parametrize(("over", "code"), _LEGACY)
def test_loading_a_legacy_question_is_lenient_but_admin_create_and_update_are_strict(over, code):
    args = dict(
        topic_id=TOPIC_ID, text="q?", options=_opts("a", "b"), correct_option_id="a", explanation="because"
    ) | over
    legacy = QuizQuestion(id=uuid4(), **args)  # the DB-loader path: only grading invariants
    with pytest.raises(InvalidQuizQuestionException) as err:
        QuizQuestion.create(**args)
    assert err.value.code == code
    with pytest.raises(InvalidQuizQuestionException) as err:
        legacy.update(active=False)  # the whole resulting question is validated
    assert err.value.code == code and legacy.active is True


def test_question_loaded_with_no_explanation_gets_an_empty_one():
    q = QuizQuestion(uuid4(), TOPIC_ID, "q", _opts("a", "b"), "a", None)
    assert q.explanation == ""


def test_loading_a_legacy_topic_slug_is_lenient_but_rename_validates():
    legacy = QuizTopic(uuid4(), "Old_Slug", "Old")
    with pytest.raises(InvalidQuizTopicException) as err:
        legacy.renamed("New")
    assert err.value.code == "invalid_slug"
    with pytest.raises(InvalidQuizTopicException):
        QuizTopic.create("Old_Slug", "Old")
    assert QuizTopic.create("ok", "x").renamed("  New ", False).label == "New"
