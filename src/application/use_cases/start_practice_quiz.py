"""Use case: start a new practice quiz on a topic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from src.application.dtos.quiz import QuizOutputDTO
from src.application.ports.coin_repository import CoinRepositoryProtocol
from src.application.ports.quiz_repository import QuizRepositoryProtocol
from src.application.use_cases.quiz_support import QuizRewards, quiz_output
from src.domain.entities.quiz import Quiz, ensure_date_in_window, pick_questions
from src.domain.enums import QuizKind
from src.domain.exceptions import QuizTopicNotFoundException


@dataclass
class StartPracticeQuizUseCase:
    quizzes: QuizRepositoryProtocol
    coins: CoinRepositoryProtocol
    rewards: QuizRewards

    async def execute(self, user_id: int, topic_slug: str, day: date) -> QuizOutputDTO:
        """``day`` is the client's local day; it fixes which day's coin cap this quiz counts against."""
        ensure_date_in_window(day, datetime.now(UTC).date())
        topic = await self.quizzes.get_topic_by_slug(topic_slug)
        if topic is None:
            raise QuizTopicNotFoundException(f"no quiz topic {topic_slug!r}")
        picked = pick_questions(
            await self.quizzes.active_questions(topic.id), await self.quizzes.seen_question_ids(user_id)
        )
        quiz = await self.quizzes.add(Quiz.create(user_id, QuizKind.PRACTICE, day, picked, topic))
        return await quiz_output(quiz, self.quizzes, self.coins, self.rewards)
