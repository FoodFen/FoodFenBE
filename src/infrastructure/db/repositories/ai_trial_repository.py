"""Concrete ``AiTrialRepositoryProtocol`` backed by async SQLAlchemy."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.ai_trial_limits import DEFAULT_AI_TRIAL_LIMITS, AiTrialLimits
from src.domain.enums import AiTrialMethod
from src.infrastructure.db.models.ai_trial_limits_model import AiTrialLimitsORM
from src.infrastructure.db.models.ai_trial_usage_model import AiTrialUsageORM


class SQLAlchemyAiTrialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def used(self, owner_keys: Sequence[str], day: date) -> dict[AiTrialMethod, int]:
        rows = await self._session.execute(
            select(AiTrialUsageORM.input_method, func.max(AiTrialUsageORM.used))
            .where(AiTrialUsageORM.owner_key.in_(owner_keys), AiTrialUsageORM.day == day)
            .group_by(AiTrialUsageORM.input_method)
        )
        return {method: used for method, used in rows}

    async def increment(self, owner_keys: Sequence[str], method: AiTrialMethod, day: date) -> None:
        for key in owner_keys:
            await self._session.execute(
                pg_insert(AiTrialUsageORM)
                .values(id=uuid4(), owner_key=key, input_method=method, day=day, used=1)
                .on_conflict_do_update(
                    index_elements=["owner_key", "input_method", "day"],
                    set_={"used": AiTrialUsageORM.used + 1},
                )
            )

    async def limits(self) -> AiTrialLimits:
        row = await self._session.scalar(select(AiTrialLimitsORM).limit(1))
        return AiTrialLimits(row.guest_limit, row.signed_in_limit) if row else DEFAULT_AI_TRIAL_LIMITS

    async def save_limits(self, limits: AiTrialLimits) -> None:
        row = await self._session.scalar(select(AiTrialLimitsORM).limit(1))
        if row is None:
            row = AiTrialLimitsORM(id=uuid4())
            self._session.add(row)
        row.guest_limit, row.signed_in_limit = limits.guest, limits.signed_in
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
