"""Use case: log an exercise session."""

from __future__ import annotations

from dataclasses import dataclass

from src.application.dtos.activity_log import ActivityLogOutputDTO, CreateActivityLogInputDTO
from src.application.ports.activity_log_repository import ActivityLogRepositoryProtocol
from src.domain.entities.activity_log import ActivityLog


@dataclass
class CreateActivityLogUseCase:
    activity_logs: ActivityLogRepositoryProtocol

    async def execute(self, input_dto: CreateActivityLogInputDTO) -> ActivityLogOutputDTO:
        log = ActivityLog.create(
            user_id=input_dto.user_id,
            activity_type=input_dto.activity_type,
            calories_burned=input_dto.calories_burned,
            client_id=input_dto.client_id,
            source=input_dto.source,
            logged_at=input_dto.logged_at,
            logged_on=input_dto.logged_on,
        )
        created = await self.activity_logs.create(log)
        return ActivityLogOutputDTO.from_entity(created)
