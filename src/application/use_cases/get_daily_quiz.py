"""Use case: today's daily quiz for a user — created lazily on first read."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from src.application.dtos.quiz import QuizOutputDTO
from src.application.ports.coin_repository import CoinRepositoryProtocol
from src.application.ports.quiz_repository import QuizRepositoryProtocol
from src.application.use_cases.quiz_support import QuizRewards, quiz_output
from src.domain.entities.quiz import Quiz, ensure_date_in_window, pick_questions
from src.domain.enums import QuizKind


@dataclass
class GetDailyQuizUseCase:
    quizzes: QuizRepositoryProtocol
    coins: CoinRepositoryProtocol
    rewards: QuizRewards

    async def execute(self, user_id: int, day: date) -> QuizOutputDTO:
        """``day`` is the client's local day."""
        ensure_date_in_window(day, datetime.now(UTC).date())
        quiz = await self.quizzes.get_daily(user_id, day)
        if quiz is None:
            picked = pick_questions(
                await self.quizzes.active_questions(None), await self.quizzes.seen_question_ids(user_id)
            )
            quiz = await self.quizzes.get_or_add_daily(
                Quiz.create(user_id, QuizKind.DAILY, day, picked)
            )
        return await quiz_output(quiz, self.quizzes, self.coins, self.rewards)
