"""Shared pieces of the quiz use cases: reward config and the player-facing output."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.quiz import (
    QuizOptionDTO,
    QuizOutputDTO,
    QuizQuestionOutputDTO,
)
from src.application.ports.coin_repository import CoinRepositoryProtocol
from src.application.ports.quiz_repository import QuizRepositoryProtocol
from src.domain.entities.quiz import Quiz
from src.domain.enums import QuizKind


@dataclass(frozen=True)
class QuizRewards:
    daily_per_correct: int
    practice_per_correct: int
    practice_daily_cap: int

    def per_correct(self, kind: QuizKind) -> int:
        return self.daily_per_correct if kind is QuizKind.DAILY else self.practice_per_correct


async def coins_remaining_today(
    quiz: Quiz, quizzes: QuizRepositoryProtocol, rewards: QuizRewards
) -> int | None:
    """What's left of the practice cap on the quiz's own date; ``None`` for daily quizzes."""
    if quiz.kind is not QuizKind.PRACTICE:
        return None
    used = await quizzes.practice_coins_earned(quiz.user_id, quiz.quiz_date)
    return max(0, rewards.practice_daily_cap - used)


async def quiz_output(
    quiz: Quiz,
    quizzes: QuizRepositoryProtocol,
    coins: CoinRepositoryProtocol,
    rewards: QuizRewards,
) -> QuizOutputDTO:
    return QuizOutputDTO(
        id=quiz.id,
        kind=quiz.kind,
        topic=quiz.topic.slug if quiz.topic else None,
        quiz_date=quiz.quiz_date,
        coins_per_correct=rewards.per_correct(quiz.kind),
        coins_remaining_today=await coins_remaining_today(quiz, quizzes, rewards),
        status="completed" if quiz.submitted else "available",
        result=None,
        questions=[
            QuizQuestionOutputDTO(
                id=q.id,
                text=q.text,
                options=[QuizOptionDTO(id=o.id, text=o.text) for o in q.options],
            )
            for q in quiz.questions
        ],
    )
