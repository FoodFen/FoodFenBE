"""Concrete ``AiTrialRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums import AiTrialMethod
from src.infrastructure.db.models.ai_trial_usage_model import AiTrialUsageORM


class SQLAlchemyAiTrialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def used(self, owner_keys: Sequence[str]) -> dict[AiTrialMethod, int]:
        rows = await self._session.execute(
            select(AiTrialUsageORM.input_method, func.max(AiTrialUsageORM.used))
            .where(AiTrialUsageORM.owner_key.in_(owner_keys))
            .group_by(AiTrialUsageORM.input_method)
        )
        return {method: used for method, used in rows}

    async def increment(self, owner_keys: Sequence[str], method: AiTrialMethod) -> None:
        for key in owner_keys:
            await self._session.execute(
                pg_insert(AiTrialUsageORM)
                .values(id=uuid4(), owner_key=key, input_method=method, used=1)
                .on_conflict_do_update(
                    index_elements=["owner_key", "input_method"],
                    set_={"used": AiTrialUsageORM.used + 1},
                )
            )
