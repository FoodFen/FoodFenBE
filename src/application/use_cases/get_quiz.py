"""Use case: re-read one of the user's own quizzes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.quiz import QuizOutputDTO
from src.application.ports.coin_repository import CoinRepositoryProtocol
from src.application.ports.quiz_repository import QuizRepositoryProtocol
from src.application.use_cases.quiz_support import QuizRewards, quiz_output
from src.domain.exceptions import QuizNotFoundException


@dataclass
class GetQuizUseCase:
    quizzes: QuizRepositoryProtocol
    coins: CoinRepositoryProtocol
    rewards: QuizRewards

    async def execute(self, user_id: int, quiz_id: UUID) -> QuizOutputDTO:
        quiz = await self.quizzes.get(quiz_id, user_id)
        if quiz is None:
            raise QuizNotFoundException(f"no quiz {quiz_id}")
        return await quiz_output(quiz, self.quizzes, self.coins, self.rewards)
