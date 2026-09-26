"""Use case: full-replace an existing water log.

For corrections after the fact (e.g. "tap a cup" shrinking an
already-synced amount), mirroring the same create/update pattern
activity-logs already has.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.water_log import UpdateWaterLogInputDTO, WaterLogOutputDTO
from src.application.ports.water_log_repository import WaterLogRepositoryProtocol
from src.domain.entities.water_log import WaterLog
from src.domain.exceptions import WaterLogNotFoundException


@dataclass
class UpdateWaterLogUseCase:
    water_logs: WaterLogRepositoryProtocol

    async def execute(
        self, user_id: int, log_id: UUID, input_dto: UpdateWaterLogInputDTO
    ) -> WaterLogOutputDTO:
        existing = await self.water_logs.get_by_id(log_id)
        if existing is None or existing.user_id != user_id:
            raise WaterLogNotFoundException(f"no water log {log_id}")

        log = WaterLog(
            id=log_id,
            user_id=user_id,
            amount_ml=input_dto.amount_ml,
            client_id=existing.client_id,
            logged_at=input_dto.logged_at or existing.logged_at,
            logged_on=input_dto.logged_on or existing.logged_on,
        )
        updated = await self.water_logs.update(log)
        return WaterLogOutputDTO.from_entity(updated)
