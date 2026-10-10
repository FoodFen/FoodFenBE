"""Use case: every quiz question, active or not, for the admin content screen."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dish_fit import fold
from src.application.dtos.admin import AdminQuizQuestionDTO
from src.application.ports.quiz_repository import QuizRepositoryProtocol


@dataclass
class ListAdminQuizQuestionsUseCase:
    quizzes: QuizRepositoryProtocol

    async def execute(self) -> list[AdminQuizQuestionDTO]:
        # folded sort: a DB collation would put Vietnamese accented letters last
        return sorted(await self.quizzes.all_questions(), key=lambda q: (fold(q.topic), fold(q.question)))
