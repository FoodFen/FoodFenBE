"""Quiz entities — a server-graded set of questions. Standard library only."""

from __future__ import annotations

import random
import re
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from src.domain.enums import CoinReason, QuizKind
from src.domain.exceptions import (
    InvalidAttributeException,
    InvalidQuizAnswersException,
    InvalidQuizDateException,
    InvalidQuizQuestionException,
    InvalidQuizTopicException,
)

QUESTIONS_PER_QUIZ = 5
DATE_WINDOW_DAYS = 1
MAX_SLUG_LENGTH = 32
MAX_LABEL_LENGTH = 64
MAX_QUESTION_TEXT_LENGTH = 500
MIN_OPTIONS, MAX_OPTIONS = 2, 4  # the app labels options A-D
MAX_OPTION_ID_LENGTH = 16
MAX_OPTION_TEXT_LENGTH = 200
MAX_EXPLANATION_LENGTH = 1000
_SLUG = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")


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
    slug: str  # immutable once created: the app sends it to POST /quizzes/practice
    label: str
    active: bool = True

    def _check_content(self) -> None:
        """Admin content rules. Not run on load, so a legacy row never breaks reading."""
        if len(self.slug) > MAX_SLUG_LENGTH or not _SLUG.fullmatch(self.slug):
            raise InvalidQuizTopicException(
                f"slug must be kebab-case (a-z, 0-9, hyphens), at most {MAX_SLUG_LENGTH} characters",
                "invalid_slug",
                "slug",
            )
        label = (self.label or "").strip()
        if not label:
            raise InvalidQuizTopicException("label must not be empty", "label_required", "label")
        if len(label) > MAX_LABEL_LENGTH:
            raise InvalidQuizTopicException(
                f"label must be at most {MAX_LABEL_LENGTH} characters", "label_too_long", "label"
            )
        object.__setattr__(self, "label", label)  # frozen: normalise in place

    @classmethod
    def create(cls, slug: str, label: str, active: bool = True) -> QuizTopic:
        topic = cls(uuid4(), slug, label, active)
        topic._check_content()
        return topic

    def renamed(self, label: str | None = None, active: bool | None = None) -> QuizTopic:
        """A validated copy with the given fields changed (the slug never changes)."""
        changed = replace(
            self,
            label=self.label if label is None else label,
            active=self.active if active is None else active,
        )
        changed._check_content()
        return changed


@dataclass
class QuizQuestion:
    id: UUID
    topic_id: UUID
    text: str
    options: list[QuizOption]
    correct_option_id: str
    explanation: str
    active: bool = True

    def __post_init__(self) -> None:
        # Only what grading needs, so a hand-edited DB row still loads; the content rules are in
        # _check_content, run on admin create/update.
        self.explanation = self.explanation or ""
        ids = [o.id for o in self.options]
        if len(ids) < MIN_OPTIONS:
            raise InvalidQuizQuestionException(
                f"a question needs at least {MIN_OPTIONS} options", "option_count", "options"
            )
        if len(set(ids)) != len(ids):
            raise InvalidQuizQuestionException("option ids must be distinct", "option_ids_not_unique", "options")
        if self.correct_option_id not in ids:
            raise InvalidQuizQuestionException(
                "correct_option_id must be one of the options", "correct_option_invalid", "correct_option_id"
            )

    def _check_content(self) -> None:
        """Admin content rules (and trimming). Raises before anything but the trimming is changed."""

        def invalid(message: str, code: str, field_name: str) -> InvalidQuizQuestionException:
            return InvalidQuizQuestionException(message, code, field_name)

        text = (self.text or "").strip()
        if not text:
            raise invalid("text must not be empty", "text_required", "text")
        if len(text) > MAX_QUESTION_TEXT_LENGTH:
            raise invalid(f"text must be at most {MAX_QUESTION_TEXT_LENGTH} characters", "text_too_long", "text")
        if len(self.options) > MAX_OPTIONS:
            raise invalid(f"a question needs {MIN_OPTIONS} to {MAX_OPTIONS} options", "option_count", "options")
        if any(not 1 <= len(o.id) <= MAX_OPTION_ID_LENGTH for o in self.options):
            raise invalid(
                f"option ids must be 1 to {MAX_OPTION_ID_LENGTH} characters", "option_id_invalid", "options"
            )
        cleaned = []
        for index, option in enumerate(self.options):
            option_text = (option.text or "").strip()
            if not option_text:
                raise invalid("option text must not be empty", "option_text_required", f"options.{index}.text")
            if len(option_text) > MAX_OPTION_TEXT_LENGTH:
                raise invalid(
                    f"option text must be at most {MAX_OPTION_TEXT_LENGTH} characters",
                    "option_text_too_long",
                    f"options.{index}.text",
                )
            cleaned.append(QuizOption(option.id, option_text))
        explanation = self.explanation.strip()
        if len(explanation) > MAX_EXPLANATION_LENGTH:
            raise invalid(
                f"explanation must be at most {MAX_EXPLANATION_LENGTH} characters",
                "explanation_too_long",
                "explanation",
            )
        self.text, self.options, self.explanation = text, cleaned, explanation

    @classmethod
    def create(
        cls,
        topic_id: UUID,
        text: str,
        options: list[QuizOption],
        correct_option_id: str,
        explanation: str = "",
        active: bool = True,
    ) -> QuizQuestion:
        question = cls(uuid4(), topic_id, text, options, correct_option_id, explanation, active)
        question._check_content()
        return question

    def update(
        self,
        topic_id: UUID | None = None,
        text: str | None = None,
        options: list[QuizOption] | None = None,
        correct_option_id: str | None = None,
        explanation: str | None = None,
        active: bool | None = None,
    ) -> None:
        """Only the given fields change; the whole result is validated before self is touched."""
        changed = replace(
            self,
            topic_id=self.topic_id if topic_id is None else topic_id,
            text=self.text if text is None else text,
            options=self.options if options is None else options,
            correct_option_id=self.correct_option_id if correct_option_id is None else correct_option_id,
            explanation=self.explanation if explanation is None else explanation,
            active=self.active if active is None else active,
        )  # replace() re-runs __post_init__ (grading invariants)
        changed._check_content()
        vars(self).update(vars(changed))


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
