"""Use case: list activity logs in an inclusive date range."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from src.application.dtos.activity_log import ActivityLogOutputDTO
from src.application.ports.activity_log_repository import ActivityLogRepositoryProtocol


@dataclass
class ListActivityLogsUseCase:
    activity_logs: ActivityLogRepositoryProtocol

    async def execute(self, user_id: int, from_date: date, to_date: date) -> list[ActivityLogOutputDTO]:
        logs = await self.activity_logs.list_by_date_range(user_id, from_date, to_date)
        return [ActivityLogOutputDTO.from_entity(log) for log in logs]
