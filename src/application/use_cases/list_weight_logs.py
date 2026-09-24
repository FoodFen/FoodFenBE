"""Use case: list weight logs in an inclusive date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.application.dtos.weight_log import WeightLogOutputDTO
from src.application.ports.weight_log_repository import WeightLogRepositoryProtocol


@dataclass
class ListWeightLogsUseCase:
    weight_logs: WeightLogRepositoryProtocol

    async def execute(self, user_id: int, from_date: date, to_date: date) -> list[WeightLogOutputDTO]:
        logs = await self.weight_logs.list_by_date_range(user_id, from_date, to_date)
        return [WeightLogOutputDTO.from_entity(log) for log in logs]
