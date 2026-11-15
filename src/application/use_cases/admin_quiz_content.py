"""Use cases: admin management of quiz topics and questions.

Field rules live in the ``QuizTopic`` / ``QuizQuestion`` entities. The one rule that needs the DB: a
question already in an issued quiz keeps its option ids and correct answer (grading and results re-read
them live), so only its wording can change and it can't be deleted.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dish_fit import fold
from src.application.dtos.admin import AdminQuizQuestionDTO, AdminQuizTopicDTO
from src.application.dtos.quiz import QuizOptionDTO
from src.application.ports.quiz_repository import QuizRepositoryProtocol
from src.domain.entities.quiz import QuizOption, QuizQuestion, QuizTopic
from src.domain.exceptions import (
    InvalidQuizQuestionException,
    QuizQuestionInUseException,
    QuizQuestionNotFoundException,
    QuizTopicNotFoundException,
    QuizTopicSlugTakenException,
)


def _options(options: list[QuizOptionDTO] | None) -> list[QuizOption] | None:
    return None if options is None else [QuizOption(o.id, o.text) for o in options]


async def _topic(quizzes: QuizRepositoryProtocol, topic_id: UUID) -> QuizTopic:
    topic = await quizzes.get_topic(topic_id)
    if topic is None:
        raise QuizTopicNotFoundException(f"no quiz topic {topic_id}")
    return topic


async def _question_dto(quizzes: QuizRepositoryProtocol, question: QuizQuestion) -> AdminQuizQuestionDTO:
    topic = await quizzes.get_topic(question.topic_id)
    if topic is None:  # a body topicId naming nothing; the FK would otherwise surface as a 500
        raise InvalidQuizQuestionException(f"no quiz topic {question.topic_id}", "unknown_topic", "topic_id")
    return AdminQuizQuestionDTO.from_entity(question, topic.label)


@dataclass
class ListAdminQuizTopicsUseCase:
    quizzes: QuizRepositoryProtocol

    async def execute(self) -> list[AdminQuizTopicDTO]:
        # folded sort: a DB collation would put Vietnamese accented letters last
        return sorted(await self.quizzes.admin_topics(), key=lambda t: fold(t.label))


@dataclass
class CreateQuizTopicUseCase:
    quizzes: QuizRepositoryProtocol

    async def execute(self, slug: str, label: str, active: bool) -> AdminQuizTopicDTO:
        topic = QuizTopic.create(slug, label, active)
        if await self.quizzes.topic_slug_exists(topic.slug):
            raise QuizTopicSlugTakenException(f"a quiz topic with slug '{topic.slug}' already exists")
        await self.quizzes.add_topic(topic)
        return AdminQuizTopicDTO(topic.id, topic.slug, topic.label, topic.active, 0)


@dataclass
class UpdateQuizTopicUseCase:
    """The slug is immutable: the app sends it to ``POST /quizzes/practice``."""

    quizzes: QuizRepositoryProtocol

    async def execute(self, topic_id: UUID, label: str | None, active: bool | None) -> AdminQuizTopicDTO:
        topic = await _topic(self.quizzes, topic_id)
        topic = topic.renamed(label, active)
        await self.quizzes.update_topic(topic)
        count = next(t.active_question_count for t in await self.quizzes.admin_topics() if t.id == topic.id)
        return AdminQuizTopicDTO(topic.id, topic.slug, topic.label, topic.active, count)


@dataclass
class CreateQuizQuestionUseCase:
    quizzes: QuizRepositoryProtocol

    async def execute(
        self,
        topic_id: UUID,
        text: str,
        options: list[QuizOptionDTO],
        correct_option_id: str,
        explanation: str,
        active: bool,
    ) -> AdminQuizQuestionDTO:
        question = QuizQuestion.create(topic_id, text, _options(options), correct_option_id, explanation, active)
        dto = await _question_dto(self.quizzes, question)
        await self.quizzes.add_question(question)
        return dto


@dataclass
class UpdateQuizQuestionUseCase:
    quizzes: QuizRepositoryProtocol

    async def execute(
        self,
        question_id: UUID,
        topic_id: UUID | None,
        text: str | None,
        options: list[QuizOptionDTO] | None,
        correct_option_id: str | None,
        explanation: str | None,
        active: bool | None,
    ) -> AdminQuizQuestionDTO:
        question = await self.quizzes.get_question(question_id)
        if question is None:
            raise QuizQuestionNotFoundException(f"no quiz question {question_id}")
        answer = ({o.id for o in question.options}, question.correct_option_id)
        question.update(topic_id, text, _options(options), correct_option_id, explanation, active)
        dto = await _question_dto(self.quizzes, question)
        if answer != ({o.id for o in question.options}, question.correct_option_id) and (
            await self.quizzes.question_in_use(question_id)
        ):
            raise QuizQuestionInUseException(
                "this question is already in a player's quiz, so its option ids and correct answer are "
                "frozen; deactivate it and create a new question instead"
            )
        await self.quizzes.update_question(question)
        return dto


@dataclass
class DeleteQuizQuestionUseCase:
    quizzes: QuizRepositoryProtocol

    async def execute(self, question_id: UUID) -> None:
        if await self.quizzes.get_question(question_id) is None:
            raise QuizQuestionNotFoundException(f"no quiz question {question_id}")
        if await self.quizzes.question_in_use(question_id):
            raise QuizQuestionInUseException(
                "this question is already in a player's quiz and can't be deleted; "
                "deactivate it and create a new question instead"
            )
        await self.quizzes.delete_question(question_id)
