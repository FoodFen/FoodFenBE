"""CreateActivityLogUseCase / UpdateActivityLogUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

import pytest

from src.application.dtos.activity_log import CreateActivityLogInputDTO, UpdateActivityLogInputDTO
from src.application.use_cases.create_activity_log import CreateActivityLogUseCase
from src.application.use_cases.update_activity_log import UpdateActivityLogUseCase
from src.domain.entities.activity_log import ActivityLog
from src.domain.enums import ActivitySource
from src.domain.exceptions import ActivityLogNotFoundException


class FakeActivityLogRepo:
    def __init__(self) -> None:
        self._by_id: dict = {}
        self._by_client_id: dict = {}

    async def create(self, log: ActivityLog) -> ActivityLog:
        key = (log.user_id, log.client_id)
        if key in self._by_client_id:
            return self._by_client_id[key]
        self._by_id[log.id] = log
        self._by_client_id[key] = log
        return log

    async def get_by_id(self, log_id):
        return self._by_id.get(log_id)

    async def update(self, log: ActivityLog) -> ActivityLog:
        if self._by_id.get(log.id) is None:
            raise ActivityLogNotFoundException(f"no activity log {log.id}")
        self._by_id[log.id] = log
        return log

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._by_id.values()
            if log.user_id == user_id and from_date <= log.logged_on <= to_date
        ]


def _create_dto(client_id="activity_1") -> CreateActivityLogInputDTO:
    return CreateActivityLogInputDTO(
        user_id=1, activity_type="running", calories_burned=300, client_id=client_id
    )


async def test_create_returns_dto_with_assigned_id():
    use_case = CreateActivityLogUseCase(activity_logs=FakeActivityLogRepo())
    result = await use_case.execute(_create_dto())
    assert result.activity_type == "running"
    assert result.user_id == 1


async def test_create_with_repeated_client_id_returns_the_same_log():
    repo = FakeActivityLogRepo()
    use_case = CreateActivityLogUseCase(activity_logs=repo)
    first = await use_case.execute(_create_dto())
    second = await use_case.execute(_create_dto())
    assert second.id == first.id


async def test_update_replaces_fields_for_the_owner():
    repo = FakeActivityLogRepo()
    created = await CreateActivityLogUseCase(activity_logs=repo).execute(_create_dto())

    use_case = UpdateActivityLogUseCase(activity_logs=repo)
    result = await use_case.execute(
        user_id=1,
        log_id=created.id,
        input_dto=UpdateActivityLogInputDTO(
            activity_type="swimming", calories_burned=450, source=ActivitySource.MANUAL
        ),
    )
    assert result.activity_type == "swimming"
    assert result.calories_burned == 450


async def test_update_raises_not_found_for_another_users_log():
    repo = FakeActivityLogRepo()
    created = await CreateActivityLogUseCase(activity_logs=repo).execute(_create_dto())

    use_case = UpdateActivityLogUseCase(activity_logs=repo)
    with pytest.raises(ActivityLogNotFoundException):
        await use_case.execute(
            user_id=999,
            log_id=created.id,
            input_dto=UpdateActivityLogInputDTO(activity_type="x", calories_burned=1),
        )
