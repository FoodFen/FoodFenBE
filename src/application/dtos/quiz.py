"""Quiz DTOs — frozen dataclasses, never Pydantic models or ORM rows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from src.domain.entities.quiz import Quiz
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

    @classmethod
    def from_entity(
        cls, quiz: Quiz, balance: int, coins_remaining_today: int | None
    ) -> QuizResultDTO:
        answers = [
            QuizAnswerResultDTO(
                question_id=q.id,
                selected_option_id=quiz.answers[q.id],
                correct_option_id=q.correct_option_id,
                correct=quiz.answers[q.id] == q.correct_option_id,
                explanation=q.explanation,
            )
            for q in quiz.questions
        ]
        return cls(
            quiz_id=quiz.id,
            correct_count=quiz.correct_count,
            total=len(quiz.questions),
            answers=answers,
            coins_earned=quiz.coins_earned,
            balance=balance,
            coins_remaining_today=coins_remaining_today,
        )


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
