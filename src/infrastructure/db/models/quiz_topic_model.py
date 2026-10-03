"""ORM model for quiz topics."""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.entities.quiz import QuizTopic
from src.infrastructure.db.base import Base
from src.infrastructure.db.mixins import UUIDPrimaryKey


class QuizTopicORM(UUIDPrimaryKey, Base):
    __tablename__ = "quiz_topics"
    __table_args__ = (UniqueConstraint("slug", name="uq_quiz_topics_slug"),)

    slug: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    def to_domain(self) -> QuizTopic:
        return QuizTopic(id=self.id, slug=self.slug, label=self.label)
