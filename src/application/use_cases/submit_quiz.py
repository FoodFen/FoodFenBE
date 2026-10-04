"""Use case: grade a quiz and pay coins through the ledger."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.quiz import QuizAnswerInputDTO, QuizResultDTO
from src.application.ports.coin_repository import CoinRepositoryProtocol
from src.application.ports.quiz_repository import QuizRepositoryProtocol
from src.application.use_cases.quiz_support import QuizRewards, quiz_result
from src.domain.entities.coin_transaction import CoinTransaction
from src.domain.enums import QuizKind
from src.domain.exceptions import QuizAlreadySubmittedException, QuizNotFoundException


@dataclass
class SubmitQuizUseCase:
    quizzes: QuizRepositoryProtocol
    coins: CoinRepositoryProtocol
    rewards: QuizRewards

    async def execute(
        self, user_id: int, quiz_id: UUID, answers: list[QuizAnswerInputDTO]
    ) -> QuizResultDTO:
        quiz = await self.quizzes.get(quiz_id, user_id)
        if quiz is None:
            raise QuizNotFoundException(f"no quiz {quiz_id}")
        if quiz.submitted:
            raise QuizAlreadySubmittedException(f"quiz {quiz_id} was already submitted")

        pairs = [(a.question_id, a.option_id) for a in answers]
        correct = quiz.grade(pairs)
        earned = correct * self.rewards.per_correct(quiz.kind)
        if quiz.kind is QuizKind.PRACTICE:
            # Lock the user row so two concurrent practice submits can't both read the same
            # `used` and overshoot the cap (same trick as coin redeem).
            await self.coins.balance(user_id, for_update=True)
            used = await self.quizzes.practice_coins_earned(user_id, quiz.quiz_date)
            earned = min(earned, max(0, self.rewards.practice_daily_cap - used))

        quiz.mark_submitted(pairs, correct, earned)
        # Only the request that flips submitted_at pays: a retry or a race loses here.
        if not await self.quizzes.mark_submitted(quiz):
            raise QuizAlreadySubmittedException(f"quiz {quiz_id} was already submitted")
        if earned:
            await self.coins.add(CoinTransaction.create(user_id, earned, quiz.coin_reason))
        return await quiz_result(quiz, self.quizzes, self.coins, self.rewards)
