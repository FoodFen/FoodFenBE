"""Use case: log a weigh-in."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.weight_log import CreateWeightLogInputDTO, WeightLogOutputDTO
from src.application.ports.weight_log_repository import WeightLogRepositoryProtocol
from src.domain.entities.weight_log import WeightLog


@dataclass
class CreateWeightLogUseCase:
    weight_logs: WeightLogRepositoryProtocol

    async def execute(self, input_dto: CreateWeightLogInputDTO) -> WeightLogOutputDTO:
        log = WeightLog.create(
            user_id=input_dto.user_id,
            weight=input_dto.weight,
            recorded_at=input_dto.recorded_at,
            client_id=input_dto.client_id,
        )
        created = await self.weight_logs.create(log)
        return WeightLogOutputDTO.from_entity(created)
