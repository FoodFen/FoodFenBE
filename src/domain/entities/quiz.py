"""Quiz entities — a server-graded set of questions. Standard library only."""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.enums import CoinReason, QuizKind
from src.domain.exceptions import (
    InvalidAttributeException,
    InvalidQuizAnswersException,
    InvalidQuizDateException,
)

QUESTIONS_PER_QUIZ = 5
DATE_WINDOW_DAYS = 1


def ensure_date_in_window(day: date, today: date) -> None:
    """``day`` is the client's local day. More than a day away from the server's UTC day means a
    client claiming fresh days to farm coins."""
    if abs((day - today).days) > DATE_WINDOW_DAYS:
        raise InvalidQuizDateException(f"date {day.isoformat()} is outside the allowed window")


@dataclass(frozen=True)
class QuizOption:
    id: str
    text: str


@dataclass(frozen=True)
class QuizTopic:
    id: UUID
    slug: str
    label: str


@dataclass
class QuizQuestion:
    id: UUID
    topic_id: UUID
    text: str
    options: list[QuizOption]
    correct_option_id: str
    explanation: str

    def __post_init__(self) -> None:
        ids = [o.id for o in self.options]
        if len(ids) < 2 or len(set(ids)) != len(ids):
            raise InvalidAttributeException("a question needs at least two options with distinct ids")
        if self.correct_option_id not in ids:
            raise InvalidAttributeException("correct_option_id must be one of the options")


@dataclass
class Quiz:
    id: UUID
    user_id: int
    kind: QuizKind
    quiz_date: date
    questions: list[QuizQuestion]
    topic: QuizTopic | None = None
    answers: dict[UUID, str] | None = None
    correct_count: int | None = None
    coins_earned: int | None = None
    submitted_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if len(self.questions) != QUESTIONS_PER_QUIZ:
            raise InvalidAttributeException(
                f"a quiz needs exactly {QUESTIONS_PER_QUIZ} questions, got {len(self.questions)}"
            )

    @property
    def submitted(self) -> bool:
        return self.submitted_at is not None

    @property
    def coin_reason(self) -> CoinReason:
        return CoinReason.QUIZ_DAILY if self.kind is QuizKind.DAILY else CoinReason.QUIZ_PRACTICE

    @classmethod
    def create(
        cls,
        user_id: int,
        kind: QuizKind,
        quiz_date: date,
        questions: list[QuizQuestion],
        topic: QuizTopic | None = None,
    ) -> Quiz:
        return cls(
            id=uuid4(), user_id=user_id, kind=kind, quiz_date=quiz_date, questions=questions, topic=topic
        )

    def grade(self, answers: Sequence[tuple[UUID, str]]) -> int:
        """Number of correct answers. Needs exactly one valid answer per question."""
        chosen = dict(answers)
        if len(answers) != len(self.questions) or set(chosen) != {q.id for q in self.questions}:
            raise InvalidQuizAnswersException("exactly one answer per question is required")
        for question in self.questions:
            if chosen[question.id] not in {o.id for o in question.options}:
                raise InvalidQuizAnswersException(f"unknown option for question {question.id}")
        return sum(chosen[q.id] == q.correct_option_id for q in self.questions)

    def mark_submitted(
        self, answers: Sequence[tuple[UUID, str]], correct_count: int, coins_earned: int
    ) -> None:
        self.answers = dict(answers)
        self.correct_count = correct_count
        self.coins_earned = coins_earned
        self.submitted_at = datetime.now(UTC)


def pick_questions(
    pool: Sequence[QuizQuestion],
    seen: set[UUID],
    count: int = QUESTIONS_PER_QUIZ,
    rng: random.Random = random,  # type: ignore[assignment]
) -> list[QuizQuestion]:
    """Random questions, unseen ones first; fall back to seen ones only to fill the quiz."""
    unseen = [q for q in pool if q.id not in seen]
    rng.shuffle(unseen)
    picked = unseen[:count]
    if len(picked) < count:
        repeats = [q for q in pool if q.id in seen]
        rng.shuffle(repeats)
        picked += repeats[: count - len(picked)]
    return picked
