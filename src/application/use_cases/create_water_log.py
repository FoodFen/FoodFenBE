"""Use case: log a drink."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.water_log import CreateWaterLogInputDTO, WaterLogOutputDTO
from src.application.ports.water_log_repository import WaterLogRepositoryProtocol
from src.domain.entities.water_log import WaterLog


@dataclass
class CreateWaterLogUseCase:
    water_logs: WaterLogRepositoryProtocol

    async def execute(self, input_dto: CreateWaterLogInputDTO) -> WaterLogOutputDTO:
        log = WaterLog.create(
            user_id=input_dto.user_id,
            amount_ml=input_dto.amount_ml,
            client_id=input_dto.client_id,
            logged_at=input_dto.logged_at,
            logged_on=input_dto.logged_on,
        )
        created = await self.water_logs.create(log)
        return WaterLogOutputDTO.from_entity(created)
