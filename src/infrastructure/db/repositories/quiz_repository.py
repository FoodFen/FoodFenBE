"""Concrete ``QuizRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.quiz import Quiz, QuizQuestion, QuizTopic
from src.domain.enums import QuizKind
from src.infrastructure.db.models.quiz_model import QuizORM
from src.infrastructure.db.models.quiz_question_model import QuizQuestionORM
from src.infrastructure.db.models.quiz_topic_model import QuizTopicORM


class SQLAlchemyQuizRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_topics(self) -> list[QuizTopic]:
        rows = (
            await self._session.execute(
                select(QuizTopicORM).where(QuizTopicORM.active.is_(True)).order_by(QuizTopicORM.label)
            )
        ).scalars()
        return [row.to_domain() for row in rows]

    async def get_topic_by_slug(self, slug: str) -> QuizTopic | None:
        row = await self._session.scalar(
            select(QuizTopicORM).where(QuizTopicORM.slug == slug, QuizTopicORM.active.is_(True))
        )
        return row.to_domain() if row else None

    async def active_questions(self, topic_id: UUID | None) -> list[QuizQuestion]:
        stmt = select(QuizQuestionORM).where(QuizQuestionORM.active.is_(True))
        if topic_id is not None:
            stmt = stmt.where(QuizQuestionORM.topic_id == topic_id)
        return [row.to_domain() for row in (await self._session.execute(stmt)).scalars()]

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
        await self._session.execute(
            pg_insert(QuizORM)
            .values({c.name: getattr(row, c.name) for c in QuizORM.__table__.columns})
            .on_conflict_do_nothing()  # the partial unique index uq_quizzes_user_daily_date
        )
        stored = await self.get_daily(quiz.user_id, quiz.quiz_date)
        assert stored is not None  # our insert or a concurrent one just made it
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
