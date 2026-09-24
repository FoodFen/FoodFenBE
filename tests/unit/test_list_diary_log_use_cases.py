"""ListActivityLogsUseCase / ListWaterLogsUseCase / ListWeightLogsUseCase unit tests. No I/O."""

from __future__ import annotations

from datetime import date

from src.application.use_cases.list_activity_logs import ListActivityLogsUseCase
from src.application.use_cases.list_water_logs import ListWaterLogsUseCase
from src.application.use_cases.list_weight_logs import ListWeightLogsUseCase
from src.domain.entities.activity_log import ActivityLog
from src.domain.entities.water_log import WaterLog
from src.domain.entities.weight_log import WeightLog


class FakeActivityLogRepo:
    def __init__(self, logs: list[ActivityLog] | None = None) -> None:
        self._logs = logs or []

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._logs
            if log.user_id == user_id and from_date <= log.logged_on <= to_date
        ]


class FakeWaterLogRepo:
    def __init__(self, logs: list[WaterLog] | None = None) -> None:
        self._logs = logs or []

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._logs
            if log.user_id == user_id and from_date <= log.logged_on <= to_date
        ]


class FakeWeightLogRepo:
    def __init__(self, logs: list[WeightLog] | None = None) -> None:
        self._logs = logs or []

    async def list_by_date_range(self, user_id, from_date, to_date):
        return [
            log
            for log in self._logs
            if log.user_id == user_id and from_date <= log.recorded_at <= to_date
        ]


async def test_activity_logs_empty_when_none_in_range():
    use_case = ListActivityLogsUseCase(activity_logs=FakeActivityLogRepo())
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert result == []


async def test_activity_logs_returns_dtos():
    log = ActivityLog.create(1, "running", 320, logged_on=date(2026, 1, 15))
    use_case = ListActivityLogsUseCase(activity_logs=FakeActivityLogRepo([log]))
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].activity_type == "running"
    assert result[0].logged_on == date(2026, 1, 15)


async def test_water_logs_empty_when_none_in_range():
    use_case = ListWaterLogsUseCase(water_logs=FakeWaterLogRepo())
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert result == []


async def test_water_logs_returns_dtos():
    log = WaterLog.create(1, 350, logged_on=date(2026, 1, 15))
    use_case = ListWaterLogsUseCase(water_logs=FakeWaterLogRepo([log]))
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].amount_ml == 350


async def test_weight_logs_empty_when_none_in_range():
    use_case = ListWeightLogsUseCase(weight_logs=FakeWeightLogRepo())
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert result == []


async def test_weight_logs_returns_dtos():
    log = WeightLog.create(1, 60.4, date(2026, 1, 15))
    use_case = ListWeightLogsUseCase(weight_logs=FakeWeightLogRepo([log]))
    result = await use_case.execute(1, date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result[0].weight == 60.4
