"""Quiz DTOs — frozen dataclasses, never Pydantic models or ORM rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from src.domain.enums import QuizKind


@dataclass(frozen=True)
class QuizTopicOutputDTO:
    id: str  # the topic slug
    label: str


@dataclass(frozen=True)
class QuizOptionDTO:
    id: str
    text: str


@dataclass(frozen=True)
class QuizQuestionOutputDTO:
    """A question as shown to the player — deliberately has no correct option or explanation."""

    id: UUID
    text: str
    options: list[QuizOptionDTO]


@dataclass(frozen=True)
class QuizAnswerResultDTO:
    question_id: UUID
    selected_option_id: str
    correct_option_id: str
    correct: bool
    explanation: str


@dataclass(frozen=True)
class QuizResultDTO:
    quiz_id: UUID
    correct_count: int
    total: int
    answers: list[QuizAnswerResultDTO]
    coins_earned: int
    balance: int
    coins_remaining_today: int | None


@dataclass(frozen=True)
class QuizOutputDTO:
    id: UUID
    kind: QuizKind
    topic: str | None
    quiz_date: date
    coins_per_correct: int
    coins_remaining_today: int | None
    status: str  # "available" | "completed"
    result: QuizResultDTO | None
    questions: list[QuizQuestionOutputDTO]


@dataclass(frozen=True)
class QuizAnswerInputDTO:
    question_id: UUID
    option_id: str
