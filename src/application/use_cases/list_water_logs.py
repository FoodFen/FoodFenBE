"""Use case: list water logs in an inclusive date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.application.dtos.water_log import WaterLogOutputDTO
from src.application.ports.water_log_repository import WaterLogRepositoryProtocol


@dataclass
class ListWaterLogsUseCase:
    water_logs: WaterLogRepositoryProtocol

    async def execute(self, user_id: int, from_date: date, to_date: date) -> list[WaterLogOutputDTO]:
        logs = await self.water_logs.list_by_date_range(user_id, from_date, to_date)
        return [WaterLogOutputDTO.from_entity(log) for log in logs]
