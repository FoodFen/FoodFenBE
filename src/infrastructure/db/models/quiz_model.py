"""ORM model for issued quizzes (one row per daily/practice instance)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.quiz import Quiz, QuizQuestion, QuizTopic
from src.domain.enums import QuizKind
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UserOwned, UUIDPrimaryKey
from src.infrastructure.db.types import enum_column


class QuizORM(UUIDPrimaryKey, UserOwned, Base):
    __tablename__ = "quizzes"
    # One daily quiz per user per day; a retried lazy-create can't issue a second one.
    # Practice rows are unconstrained (every POST makes a new one).
    __table_args__ = (
        Index(
            "uq_quizzes_user_daily_date",
            "user_id",
            "quiz_date",
            unique=True,
            postgresql_where=text("kind = 'daily'"),
            sqlite_where=text("kind = 'daily'"),
        ),
    )

    kind: Mapped[QuizKind] = mapped_column(enum_column(QuizKind, "quiz_kind"), nullable=False)
    topic_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("quiz_topics.id", ondelete="SET NULL"), nullable=True
    )
    quiz_date: Mapped[date] = mapped_column(Date, nullable=False)
    question_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    answers: Mapped[dict[str, str] | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    correct_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coins_earned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    def to_domain(self, questions: list[QuizQuestion], topic: QuizTopic | None) -> Quiz:
        return Quiz(
            id=self.id,
            user_id=self.user_id,
            kind=self.kind,
            quiz_date=self.quiz_date,
            questions=questions,
            topic=topic,
            answers={UUID(k): v for k, v in self.answers.items()} if self.answers else None,
            correct_count=self.correct_count,
            coins_earned=self.coins_earned,
            submitted_at=self.submitted_at,
            created_at=self.created_at,
        )

    @staticmethod
    def from_domain(quiz: Quiz) -> QuizORM:
        return QuizORM(
            id=quiz.id,
            user_id=quiz.user_id,
            kind=quiz.kind,
            topic_id=quiz.topic.id if quiz.topic else None,
            quiz_date=quiz.quiz_date,
            question_ids=[str(q.id) for q in quiz.questions],
            answers=None,
            correct_count=None,
            coins_earned=None,
            submitted_at=None,
            created_at=quiz.created_at,
        )
