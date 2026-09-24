"""CreateWeightLogUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

from src.application.dtos.weight_log import CreateWeightLogInputDTO
from src.application.use_cases.create_weight_log import CreateWeightLogUseCase
from src.domain.entities.weight_log import WeightLog


class FakeWeightLogRepo:
    def __init__(self) -> None:
        self._by_client_id: dict = {}

    async def create(self, log: WeightLog) -> WeightLog:
        key = (log.user_id, log.client_id)
        if key in self._by_client_id:
            return self._by_client_id[key]
        self._by_client_id[key] = log
        return log

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._by_client_id.values()
            if log.user_id == user_id and from_date <= log.recorded_at <= to_date
        ]


async def test_create_returns_dto():
    use_case = CreateWeightLogUseCase(weight_logs=FakeWeightLogRepo())
    result = await use_case.execute(
        CreateWeightLogInputDTO(user_id=1, weight=60.4, client_id="weight_1", recorded_at=date(2026, 1, 1))
    )
    assert result.weight == 60.4


async def test_create_with_repeated_client_id_returns_the_same_log():
    repo = FakeWeightLogRepo()
    use_case = CreateWeightLogUseCase(weight_logs=repo)
    dto = CreateWeightLogInputDTO(user_id=1, weight=60.4, client_id="weight_1")
    first = await use_case.execute(dto)
    second = await use_case.execute(dto)
    assert second.id == first.id
