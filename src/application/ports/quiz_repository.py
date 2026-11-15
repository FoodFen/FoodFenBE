"""Persistence port for quizzes, topics and the question bank."""

from __future__ import annotations

from datetime import date
from typing import Protocol
from uuid import UUID

from src.application.dtos.admin import AdminQuizQuestionDTO, AdminQuizTopicDTO
from src.domain.entities.quiz import Quiz, QuizQuestion, QuizTopic


class QuizRepositoryProtocol(Protocol):
    async def list_topics(self) -> list[QuizTopic]:
        """Active topics with at least ``QUESTIONS_PER_QUIZ`` active questions (the ones a player can practise)."""
        ...

    async def get_topic_by_slug(self, slug: str) -> QuizTopic | None: ...

    async def active_questions(self, topic_id: UUID | None) -> list[QuizQuestion]:
        """Active questions of one topic, or of every topic when ``topic_id`` is None. Questions of an
        inactive topic are never returned."""
        ...

    async def all_questions(self) -> list[AdminQuizQuestionDTO]:
        """Every question, active or not, in no particular order."""
        ...

    async def admin_topics(self) -> list[AdminQuizTopicDTO]:
        """Every topic, active or not, with its active-question count, in no particular order."""
        ...

    async def get_topic(self, topic_id: UUID) -> QuizTopic | None:
        """Any topic, active or not."""
        ...

    async def topic_slug_exists(self, slug: str) -> bool: ...

    async def add_topic(self, topic: QuizTopic) -> None: ...

    async def update_topic(self, topic: QuizTopic) -> None: ...

    async def get_question(self, question_id: UUID) -> QuizQuestion | None:
        """Any question, active or not."""
        ...

    async def add_question(self, question: QuizQuestion) -> None: ...

    async def update_question(self, question: QuizQuestion) -> None: ...

    async def delete_question(self, question_id: UUID) -> None: ...

    async def question_in_use(self, question_id: UUID) -> bool:
        """True when any issued quiz references the question."""
        ...

    async def seen_question_ids(self, user_id: int) -> set[UUID]: ...

    async def get_daily(self, user_id: int, day: date) -> Quiz | None: ...

    async def get_or_add_daily(self, quiz: Quiz) -> Quiz:
        """Insert ``quiz`` unless the user already has a daily one for that day; return the stored one."""
        ...

    async def add(self, quiz: Quiz) -> Quiz: ...

    async def get(self, quiz_id: UUID, user_id: int) -> Quiz | None:
        """The user's own quiz only; someone else's id is indistinguishable from a missing one."""
        ...

    async def practice_coins_earned(self, user_id: int, day: date) -> int:
        """Coins already paid for submitted practice quizzes dated ``day``."""
        ...

    async def mark_submitted(self, quiz: Quiz) -> bool:
        """Persist the grade, but only if the quiz is still unsubmitted. ``False`` means another
        request got there first — the caller must not pay."""
        ...
