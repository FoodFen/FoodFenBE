"""Use case: the active quiz topics."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.quiz import QuizTopicOutputDTO
from src.application.ports.quiz_repository import QuizRepositoryProtocol


@dataclass
class ListQuizTopicsUseCase:
    quizzes: QuizRepositoryProtocol

    async def execute(self) -> list[QuizTopicOutputDTO]:
        return [QuizTopicOutputDTO(id=t.slug, label=t.label) for t in await self.quizzes.list_topics()]
