"""Concrete ``QuizRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import String, cast, delete, exists, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.dtos.admin import AdminQuizQuestionDTO, AdminQuizTopicDTO
from src.domain.entities.quiz import QUESTIONS_PER_QUIZ, Quiz, QuizQuestion, QuizTopic
from src.domain.enums import QuizKind
from src.infrastructure.db.models.quiz_model import QuizORM
from src.infrastructure.db.models.quiz_question_model import QuizQuestionORM
from src.infrastructure.db.models.quiz_topic_model import QuizTopicORM


class SQLAlchemyQuizRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_topics(self) -> list[QuizTopic]:
        active_questions = (
            select(func.count())
            .where(QuizQuestionORM.topic_id == QuizTopicORM.id, QuizQuestionORM.active.is_(True))
            .scalar_subquery()
        )
        rows = (
            await self._session.execute(
                select(QuizTopicORM)
                .where(QuizTopicORM.active.is_(True), active_questions >= QUESTIONS_PER_QUIZ)
                .order_by(QuizTopicORM.label)
            )
        ).scalars()
        return [row.to_domain() for row in rows]

    async def get_topic_by_slug(self, slug: str) -> QuizTopic | None:
        row = await self._session.scalar(
            select(QuizTopicORM).where(QuizTopicORM.slug == slug, QuizTopicORM.active.is_(True))
        )
        return row.to_domain() if row else None

    async def active_questions(self, topic_id: UUID | None) -> list[QuizQuestion]:
        stmt = (
            select(QuizQuestionORM)
            .join(QuizTopicORM, QuizTopicORM.id == QuizQuestionORM.topic_id)
            .where(QuizQuestionORM.active.is_(True), QuizTopicORM.active.is_(True))
        )
        if topic_id is not None:
            stmt = stmt.where(QuizQuestionORM.topic_id == topic_id)
        return [row.to_domain() for row in (await self._session.execute(stmt)).scalars()]

    async def all_questions(self) -> list[AdminQuizQuestionDTO]:
        rows = await self._session.execute(
            select(QuizQuestionORM, QuizTopicORM.label).join(
                QuizTopicORM, QuizTopicORM.id == QuizQuestionORM.topic_id
            )
        )
        return [AdminQuizQuestionDTO.from_entity(q.to_domain(), label) for q, label in rows.all()]

    async def admin_topics(self) -> list[AdminQuizTopicDTO]:
        active_questions = (
            select(func.count())
            .where(QuizQuestionORM.topic_id == QuizTopicORM.id, QuizQuestionORM.active.is_(True))
            .scalar_subquery()
        )
        rows = await self._session.execute(select(QuizTopicORM, active_questions))
        return [
            AdminQuizTopicDTO(t.id, t.slug, t.label, t.active, count) for t, count in rows.all()
        ]

    async def get_topic(self, topic_id: UUID) -> QuizTopic | None:
        row = await self._session.get(QuizTopicORM, topic_id)
        return row.to_domain() if row else None

    async def topic_slug_exists(self, slug: str) -> bool:
        return await self._session.scalar(select(exists().where(QuizTopicORM.slug == slug)))

    async def add_topic(self, topic: QuizTopic) -> None:
        self._session.add(QuizTopicORM.from_domain(topic))
        await self._session.flush()

    async def update_topic(self, topic: QuizTopic) -> None:
        await self._session.merge(QuizTopicORM.from_domain(topic))
        await self._session.flush()

    async def get_question(self, question_id: UUID) -> QuizQuestion | None:
        row = await self._session.get(QuizQuestionORM, question_id)
        return row.to_domain() if row else None

    async def add_question(self, question: QuizQuestion) -> None:
        self._session.add(QuizQuestionORM.from_domain(question))
        await self._session.flush()

    async def update_question(self, question: QuizQuestion) -> None:
        await self._session.merge(QuizQuestionORM.from_domain(question))
        await self._session.flush()

    async def delete_question(self, question_id: UUID) -> None:
        await self._session.execute(delete(QuizQuestionORM).where(QuizQuestionORM.id == question_id))

    async def question_in_use(self, question_id: UUID) -> bool:
        # ponytail: scans `quizzes` as text — fine for the admin-only, rare edit/delete paths; the
        # upgrade path is a quiz_question link table once quizzes grow large.
        return await self._session.scalar(
            select(exists().where(cast(QuizORM.question_ids, String).like(f'%"{question_id}"%')))
        )

    async def seen_question_ids(self, user_id: int) -> set[UUID]:
        # ponytail: only the latest 200 quizzes count as "seen"; a heavier player re-sees old
        # questions. Raise the limit or move to a seen-questions table if that matters.
        lists = (
            await self._session.execute(
                select(QuizORM.question_ids)
                .where(QuizORM.user_id == user_id)
                .order_by(QuizORM.created_at.desc())
                .limit(200)
            )
        ).scalars()
        return {UUID(question_id) for ids in lists for question_id in ids}

    async def get_daily(self, user_id: int, day: date) -> Quiz | None:
        row = await self._session.scalar(
            select(QuizORM).where(
                QuizORM.user_id == user_id, QuizORM.kind == QuizKind.DAILY, QuizORM.quiz_date == day
            )
        )
        return await self._load(row) if row else None

    async def get_or_add_daily(self, quiz: Quiz) -> Quiz:
        row = QuizORM.from_domain(quiz)
        inserted = await self._session.scalar(
            pg_insert(QuizORM)
            .values({c.name: getattr(row, c.name) for c in QuizORM.__table__.columns})
            .on_conflict_do_nothing()  # the partial unique index uq_quizzes_user_daily_date
            .returning(QuizORM.id)
        )
        if inserted is not None:
            return quiz  # ours won; it already holds its questions, no read-back
        stored = await self.get_daily(quiz.user_id, quiz.quiz_date)
        assert stored is not None  # a concurrent insert made it
        return stored

    async def add(self, quiz: Quiz) -> Quiz:
        self._session.add(QuizORM.from_domain(quiz))
        await self._session.flush()
        return quiz

    async def get(self, quiz_id: UUID, user_id: int) -> Quiz | None:
        row = await self._session.scalar(
            select(QuizORM).where(QuizORM.id == quiz_id, QuizORM.user_id == user_id)
        )
        return await self._load(row) if row else None

    async def practice_coins_earned(self, user_id: int, day: date) -> int:
        total = await self._session.scalar(
            select(func.coalesce(func.sum(QuizORM.coins_earned), 0)).where(
                QuizORM.user_id == user_id,
                QuizORM.kind == QuizKind.PRACTICE,
                QuizORM.quiz_date == day,
                QuizORM.submitted_at.is_not(None),
            )
        )
        return int(total)

    async def mark_submitted(self, quiz: Quiz) -> bool:
        flipped = await self._session.scalar(
            update(QuizORM)
            .where(
                QuizORM.id == quiz.id,
                QuizORM.user_id == quiz.user_id,
                QuizORM.submitted_at.is_(None),
            )
            .values(
                answers={str(question_id): option_id for question_id, option_id in quiz.answers.items()},
                correct_count=quiz.correct_count,
                coins_earned=quiz.coins_earned,
                submitted_at=quiz.submitted_at,
            )
            .returning(QuizORM.id)
        )
        return flipped is not None

    async def _load(self, row: QuizORM) -> Quiz:
        ids = [UUID(i) for i in row.question_ids]
        found = {
            q.id: q
            for q in (
                await self._session.execute(select(QuizQuestionORM).where(QuizQuestionORM.id.in_(ids)))
            ).scalars()
        }
        topic = await self._session.get(QuizTopicORM, row.topic_id) if row.topic_id else None
        return row.to_domain(
            [found[i].to_domain() for i in ids], topic.to_domain() if topic else None
        )
