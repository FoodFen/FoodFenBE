"""Use case: undo a logged drink (soft delete), for the "undo my last cup" flow."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.ports.water_log_repository import WaterLogRepositoryProtocol
from src.domain.exceptions import WaterLogNotFoundException


@dataclass
class DeleteWaterLogUseCase:
    water_logs: WaterLogRepositoryProtocol

    async def execute(self, user_id: int, log_id: UUID) -> None:
        existing = await self.water_logs.get_by_id(log_id)
        if existing is None or existing.user_id != user_id:
            raise WaterLogNotFoundException(f"no water log {log_id}")
        await self.water_logs.delete(log_id)
