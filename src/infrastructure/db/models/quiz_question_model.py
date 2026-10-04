"""ORM model for quiz questions. Questions are deactivated, never deleted: issued quizzes
reference them by id."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.quiz import QuizOption, QuizQuestion
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey


class QuizQuestionORM(UUIDPrimaryKey, Base):
    __tablename__ = "quiz_questions"

    topic_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("quiz_topics.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # [{"id": "a", "text": "..."}, ...] — options are never queried individually.
    options: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    correct_option_id: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))

    def to_domain(self) -> QuizQuestion:
        return QuizQuestion(
            id=self.id,
            topic_id=self.topic_id,
            text=self.text,
            options=[QuizOption(id=o["id"], text=o["text"]) for o in self.options],
            correct_option_id=self.correct_option_id,
            explanation=self.explanation,
        )
