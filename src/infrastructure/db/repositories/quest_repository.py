"""Concrete ``QuestRepositoryProtocol`` backed by async SQLAlchemy.

``measure`` is where each quest type's meaning lives — the catalog row only carries
its target/reward/cadence.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.quest import Quest
from src.domain.entities.quest_definition import QuestDefinition
from src.domain.enums import MealType, QuestType
from src.infrastructure.db.models.daily_goal_model import DailyGoalORM
from src.infrastructure.db.models.food_entry_model import FoodEntryORM
from src.infrastructure.db.models.quest_definition_model import QuestDefinitionORM
from src.infrastructure.db.models.quest_model import QuestORM
from src.infrastructure.db.models.water_log_model import WaterLogORM
from src.infrastructure.db.models.weight_log_model import WeightLogORM

_MAIN_MEALS = (MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER)


def _percent(consumed: float, goal: float) -> int:
    """Whole percent of ``goal`` reached, capped at 100. No goal (or a zero one) scores 0."""
    return min(100, int(100 * consumed / goal)) if goal else 0


class SQLAlchemyQuestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def active_definitions(self) -> list[QuestDefinition]:
        rows = (
            await self._session.execute(
                select(QuestDefinitionORM)
                .where(QuestDefinitionORM.active.is_(True))
                .order_by(QuestDefinitionORM.quest_type)
            )
        ).scalars()
        return [row.to_domain() for row in rows]

    async def get_or_issue(self, quest: Quest) -> Quest:
        row = QuestORM.from_domain(quest)
        await self._session.execute(
            pg_insert(QuestORM)
            .values({c.name: getattr(row, c.name) for c in QuestORM.__table__.columns})
            .on_conflict_do_nothing(constraint="uq_quests_user_type_date")
        )
        stored = await self._session.scalar(
            select(QuestORM).where(
                QuestORM.user_id == quest.user_id,
                QuestORM.quest_type == quest.quest_type,
                QuestORM.quest_date == quest.quest_date,
            )
        )
        return stored.to_domain()

    async def record(self, quest: Quest) -> bool:
        updated = await self._session.scalar(
            update(QuestORM)
            .where(QuestORM.id == quest.id, QuestORM.completed.is_(False))
            .values(progress=quest.progress, completed=quest.completed)
            .returning(QuestORM.id)
        )
        return updated is not None and quest.completed

    async def measure(self, user_id: int, quest_type: QuestType, quest_date: date) -> int:
        day = quest_date
        meals = (
            FoodEntryORM.user_id == user_id,
            FoodEntryORM.logged_on == day,
            FoodEntryORM.deleted_at.is_(None),
        )
        match quest_type:
            case QuestType.LOG_BREAKFAST:
                return await self._scalar(
                    select(func.count()).where(*meals, FoodEntryORM.meal_type == MealType.BREAKFAST)
                )
            case QuestType.LOG_ALL_MEALS:
                return await self._scalar(
                    select(func.count(func.distinct(FoodEntryORM.meal_type))).where(
                        *meals, FoodEntryORM.meal_type.in_(_MAIN_MEALS)
                    )
                )
            case QuestType.HIT_CALORIE_GOAL:
                eaten = await self._scalar(select(func.sum(FoodEntryORM.total_kcal)).where(*meals))
                goal = await self._goal(user_id, day)
                return _percent(eaten, goal.target_kcal if goal else 0)
            case QuestType.HIT_PROTEIN_GOAL:
                eaten = await self._scalar(select(func.sum(FoodEntryORM.protein_g)).where(*meals))
                goal = await self._goal(user_id, day)
                return _percent(eaten, goal.target_protein_g if goal else 0)
            case QuestType.DRINK_WATER:
                drunk = await self._scalar(
                    select(func.sum(WaterLogORM.amount_ml)).where(
                        WaterLogORM.user_id == user_id,
                        WaterLogORM.logged_on == day,
                        WaterLogORM.deleted_at.is_(None),
                    )
                )
                goal = await self._goal(user_id, day)
                return _percent(drunk, goal.target_water_ml if goal else 0)
            case QuestType.LOG_WEIGHT:
                return await self._scalar(
                    select(func.count()).select_from(WeightLogORM).where(
                        WeightLogORM.user_id == user_id, WeightLogORM.recorded_at == day
                    )
                )
            case QuestType.STAY_ACTIVE_WEEK:
                return await self._scalar(
                    select(func.count(func.distinct(FoodEntryORM.logged_on))).where(
                        FoodEntryORM.user_id == user_id,
                        FoodEntryORM.logged_on >= day,
                        FoodEntryORM.logged_on <= day + timedelta(days=6),
                        FoodEntryORM.deleted_at.is_(None),
                    )
                )
        raise NotImplementedError(f"no progress evaluator for quest type {quest_type!r}")

    async def _scalar(self, stmt) -> int:
        return (await self._session.scalar(stmt)) or 0

    async def _goal(self, user_id: int, day: date) -> DailyGoalORM | None:
        return await self._session.scalar(
            select(DailyGoalORM)
            .where(DailyGoalORM.user_id == user_id, DailyGoalORM.effective_date <= day)
            .order_by(DailyGoalORM.effective_date.desc())
            .limit(1)
        )
