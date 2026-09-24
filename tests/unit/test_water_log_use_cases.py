"""CreateWaterLogUseCase / DeleteWaterLogUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from src.application.dtos.water_log import CreateWaterLogInputDTO
from src.application.use_cases.create_water_log import CreateWaterLogUseCase
from src.application.use_cases.delete_water_log import DeleteWaterLogUseCase
from src.domain.entities.water_log import WaterLog
from src.domain.exceptions import WaterLogNotFoundException


class FakeWaterLogRepo:
    def __init__(self) -> None:
        self._by_id: dict = {}
        self._by_client_id: dict = {}

    async def create(self, log: WaterLog) -> WaterLog:
        key = (log.user_id, log.client_id)
        if key in self._by_client_id:
            return self._by_client_id[key]
        self._by_id[log.id] = log
        self._by_client_id[key] = log
        return log

    async def get_by_id(self, log_id):
        return self._by_id.get(log_id)

    async def delete(self, log_id):
        if self._by_id.get(log_id) is None:
            raise WaterLogNotFoundException(f"no water log {log_id}")
        self._by_id[log_id] = None

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._by_id.values()
            if log is not None and log.user_id == user_id and from_date <= log.logged_on <= to_date
        ]


def _dto(client_id="water_1") -> CreateWaterLogInputDTO:
    return CreateWaterLogInputDTO(user_id=1, amount_ml=350, client_id=client_id)


async def test_create_returns_dto():
    use_case = CreateWaterLogUseCase(water_logs=FakeWaterLogRepo())
    result = await use_case.execute(_dto())
    assert result.amount_ml == 350


async def test_create_with_repeated_client_id_returns_the_same_log():
    repo = FakeWaterLogRepo()
    use_case = CreateWaterLogUseCase(water_logs=repo)
    first = await use_case.execute(_dto())
    second = await use_case.execute(_dto())
    assert second.id == first.id


async def test_create_stores_an_explicit_logged_at_instead_of_the_servers_clock():
    """An offline-created drink pushed later must keep its real event time
    — deriving it from the server's clock at push time would silently
    move every offline entry to whenever the sync happened to run."""
    explicit = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    use_case = CreateWaterLogUseCase(water_logs=FakeWaterLogRepo())
    result = await use_case.execute(
        CreateWaterLogInputDTO(user_id=1, amount_ml=350, client_id="water_1", logged_at=explicit)
    )
    assert result.logged_at == explicit


async def test_delete_removes_the_owners_log():
    repo = FakeWaterLogRepo()
    created = await CreateWaterLogUseCase(water_logs=repo).execute(_dto())

    use_case = DeleteWaterLogUseCase(water_logs=repo)
    await use_case.execute(user_id=1, log_id=created.id)

    assert await repo.get_by_id(created.id) is None


async def test_delete_raises_not_found_for_another_users_log():
    repo = FakeWaterLogRepo()
    created = await CreateWaterLogUseCase(water_logs=repo).execute(_dto())

    use_case = DeleteWaterLogUseCase(water_logs=repo)
    with pytest.raises(WaterLogNotFoundException):
        await use_case.execute(user_id=999, log_id=created.id)
