"""Use case: full-replace an existing activity log."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.application.dtos.activity_log import ActivityLogOutputDTO, UpdateActivityLogInputDTO
from src.application.ports.activity_log_repository import ActivityLogRepositoryProtocol
from src.domain.entities.activity_log import ActivityLog
from src.domain.exceptions import ActivityLogNotFoundException


@dataclass
class UpdateActivityLogUseCase:
    activity_logs: ActivityLogRepositoryProtocol

    async def execute(
        self, user_id: int, log_id: UUID, input_dto: UpdateActivityLogInputDTO
    ) -> ActivityLogOutputDTO:
        existing = await self.activity_logs.get_by_id(log_id)
        if existing is None or existing.user_id != user_id:
            raise ActivityLogNotFoundException(f"no activity log {log_id}")

        log = ActivityLog(
            id=log_id,
            user_id=user_id,
            activity_type=input_dto.activity_type,
            calories_burned=input_dto.calories_burned,
            client_id=existing.client_id,
            source=input_dto.source,
            logged_at=existing.logged_at,
            logged_on=input_dto.logged_on or existing.logged_on,
        )
        updated = await self.activity_logs.update(log)
        return ActivityLogOutputDTO.from_entity(updated)
